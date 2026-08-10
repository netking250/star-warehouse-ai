"""Authentication context, JWT validation, and authorization dependencies."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import timedelta
from enum import StrEnum
from uuid import uuid4

import jwt
import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings
from app.core.logging import get_correlation_id
from app.core.redis import get_redis_client
from app.core.tenancy import namespaced_key, set_current_tenant_id, validate_tenant_id
from app.core.utils import utc_now

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/login", auto_error=False)


class Role(StrEnum):
    """Roles supported by the Star Warehouse AI authorization model."""

    SUPER_ADMIN = "super_admin"
    KNOWLEDGE_ADMIN = "knowledge_admin"
    SERVICE_SUPERVISOR = "service_supervisor"
    REVIEWER = "reviewer"
    ANALYST = "analyst"
    AUDITOR = "auditor"
    CUSTOMER = "customer"


ROLE_SCOPES: dict[Role, frozenset[str]] = {
    Role.SUPER_ADMIN: frozenset({"*"}),
    Role.KNOWLEDGE_ADMIN: frozenset(
        {"knowledge:read", "knowledge:write", "knowledge:publish", "knowledge:rollback"}
    ),
    Role.SERVICE_SUPERVISOR: frozenset(
        {"conversation:read", "review:read", "review:assign", "analytics:read"}
    ),
    Role.REVIEWER: frozenset({"review:read", "review:decide"}),
    Role.ANALYST: frozenset({"analytics:read", "evaluation:read"}),
    Role.AUDITOR: frozenset({"audit:read", "conversation:read"}),
    Role.CUSTOMER: frozenset({"chat:use", "profile:read"}),
}


class _TokenClaims(BaseModel):
    """Validated access-token claims."""

    sub: str
    exp: int
    iat: int
    iss: str
    aud: str | list[str]
    jti: str
    tenant_id: str
    roles: list[Role] = Field(min_length=1)
    scopes: list[str]
    session_id: str
    is_admin: bool = False


@dataclass(frozen=True, slots=True)
class AuthContext:
    """Immutable identity and authorization context for one request."""

    tenant_id: str
    user_id: int
    roles: frozenset[Role]
    scopes: frozenset[str]
    session_id: str
    correlation_id: str
    token_id: str
    expires_at: int = field(default=0, compare=False)

    def has_role(self, role: Role) -> bool:
        """Return whether the identity has the requested role."""
        return Role.SUPER_ADMIN in self.roles or role in self.roles

    def has_scope(self, scope: str) -> bool:
        """Return whether the identity has the requested scope."""
        return "*" in self.scopes or scope in self.scopes


def extract_bearer_token(auth_header: str) -> str | None:
    """Extract a bearer token from an Authorization header."""
    if auth_header.lower().startswith("bearer ") and len(auth_header) > 7:
        return auth_header[7:]
    return None


def _validate_tenant_id(tenant_id: str) -> str:
    return validate_tenant_id(tenant_id)


def _normalize_roles(roles: Iterable[Role | str]) -> frozenset[Role]:
    normalized = frozenset(Role(role) for role in roles)
    if not normalized:
        raise ValueError("At least one role is required")
    return normalized


def scopes_for_roles(roles: Iterable[Role | str]) -> frozenset[str]:
    """Return the union of scopes granted to a collection of roles."""
    normalized_roles = _normalize_roles(roles)
    return frozenset(scope for role in normalized_roles for scope in ROLE_SCOPES[role])


def create_access_token(
    user_id: int,
    is_admin: bool = False,
    *,
    tenant_id: str = "default",
    roles: Iterable[Role | str] | None = None,
    scopes: Iterable[str] | None = None,
    session_id: str | None = None,
) -> str:
    """Create a signed access token carrying tenant and authorization claims.

    Args:
        user_id: Stable user identifier.
        is_admin: Backward-compatible administrator flag.
        tenant_id: Tenant namespace for all downstream data access.
        roles: Assigned authorization roles. Defaults from ``is_admin``.
        scopes: Explicit scopes. Defaults to the union granted by ``roles``.
        session_id: Login session identifier. A random identifier is generated when omitted.

    Returns:
        Encoded JWT access token.
    """
    validated_tenant_id = _validate_tenant_id(tenant_id)
    normalized_roles = _normalize_roles(
        roles if roles is not None else [Role.SUPER_ADMIN if is_admin else Role.CUSTOMER]
    )
    normalized_scopes = (
        frozenset(scopes) if scopes is not None else scopes_for_roles(normalized_roles)
    )
    now = utc_now()
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token_id = str(uuid4())
    to_encode = {
        "sub": str(user_id),
        "exp": expire,
        "iat": now,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "jti": token_id,
        "tenant_id": validated_tenant_id,
        "roles": sorted(role.value for role in normalized_roles),
        "scopes": sorted(normalized_scopes),
        "session_id": session_id or str(uuid4()),
        "is_admin": Role.SUPER_ADMIN in normalized_roles,
    }
    return jwt.encode(
        to_encode, settings.SECRET_KEY.get_secret_value(), algorithm=settings.ALGORITHM
    )


def _decode_token(
    token: str | None,
    *,
    headers: dict[str, str] | None = None,
    missing_user_detail: str = "Invalid token: missing user ID",
) -> _TokenClaims:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers=headers,
        )

    try:
        raw_payload: object = jwt.decode(
            token,
            settings.SECRET_KEY.get_secret_value(),
            algorithms=[settings.ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
            options={"require": ["sub", "exp", "iat", "iss", "aud", "jti", "tenant_id"]},
        )
        if isinstance(raw_payload, dict) and raw_payload.get("sub") is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=missing_user_detail,
                headers=headers,
            )
        claims = _TokenClaims.model_validate(raw_payload)
        _validate_tenant_id(claims.tenant_id)
        return claims
    except jwt.ExpiredSignatureError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers=headers,
        ) from error
    except jwt.MissingRequiredClaimError as error:
        detail = missing_user_detail if error.claim == "sub" else "Invalid token"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers=headers,
        ) from error
    except HTTPException:
        raise
    except (jwt.InvalidTokenError, ValidationError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers=headers,
        ) from error


def _context_from_claims(claims: _TokenClaims) -> AuthContext:
    try:
        user_id = int(claims.sub)
    except (ValueError, TypeError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: malformed user ID",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
    return AuthContext(
        tenant_id=claims.tenant_id,
        user_id=user_id,
        roles=frozenset(claims.roles),
        scopes=frozenset(claims.scopes),
        session_id=claims.session_id,
        correlation_id=get_correlation_id(),
        token_id=claims.jti,
        expires_at=claims.exp,
    )


async def _ensure_context_is_active(context: AuthContext, redis: aioredis.Redis) -> AuthContext:
    """Reject a token or login session that has been revoked."""
    try:
        revoked = await redis.mget(
            namespaced_key(f"auth:revoked:token:{context.token_id}", context.tenant_id),
            namespaced_key(f"auth:revoked:session:{context.session_id}", context.tenant_id),
        )
    except aioredis.RedisError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication state is temporarily unavailable",
        ) from error
    if any(revoked):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return context


async def revoke_auth_context(context: AuthContext, redis: aioredis.Redis) -> None:
    """Revoke the current token until its original expiry time."""
    ttl = max(1, context.expires_at - int(utc_now().timestamp()))
    await redis.setex(
        namespaced_key(f"auth:revoked:token:{context.token_id}", context.tenant_id),
        ttl,
        "1",
    )


def get_auth_context(token: str | None = Depends(oauth2_scheme)) -> AuthContext:
    """Validate the bearer token and return the unified request identity context."""
    claims = _decode_token(
        token,
        headers={"WWW-Authenticate": "Bearer"},
        missing_user_detail="Invalid token: missing user ID",
    )
    return _context_from_claims(claims)


async def get_active_auth_context(
    context: AuthContext = Depends(get_auth_context),
    redis: aioredis.Redis = Depends(get_redis_client),
) -> AuthContext:
    """Return a validated identity after checking revocation state."""
    active_context = await _ensure_context_is_active(context, redis)
    set_current_tenant_id(active_context.tenant_id)
    return active_context


def get_current_user_id(token: str | None = Depends(oauth2_scheme)) -> int:
    """Validate the bearer token and return its user identifier."""
    return get_auth_context(token).user_id


def get_active_user_id(context: AuthContext = Depends(get_active_auth_context)) -> int:
    """Return the user identifier from an active, non-revoked token."""
    return context.user_id


async def get_current_user_id_ws(token: str, redis: aioredis.Redis) -> int:
    """Validate a WebSocket token and return its user identifier."""
    context = _context_from_claims(_decode_token(token))
    active_context = await _ensure_context_is_active(context, redis)
    set_current_tenant_id(active_context.tenant_id)
    return active_context.user_id


async def get_admin_user_id_ws(token: str, redis: aioredis.Redis) -> int:
    """Validate an active WebSocket token and require administrator privileges."""
    context = await _ensure_context_is_active(_context_from_claims(_decode_token(token)), redis)
    set_current_tenant_id(context.tenant_id)
    if not context.has_role(Role.SUPER_ADMIN):
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return context.user_id


def require_roles(*allowed_roles: Role) -> Callable[[AuthContext], AuthContext]:
    """Create a dependency that requires at least one authorized role."""
    if not allowed_roles:
        raise ValueError("At least one allowed role is required")

    def dependency(context: AuthContext = Depends(get_active_auth_context)) -> AuthContext:
        if not any(context.has_role(role) for role in allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Required role is missing",
            )
        return context

    return dependency


def require_scopes(*required_scopes: str) -> Callable[[AuthContext], AuthContext]:
    """Create a dependency that requires every listed authorization scope."""
    if not required_scopes:
        raise ValueError("At least one required scope is required")

    def dependency(context: AuthContext = Depends(get_active_auth_context)) -> AuthContext:
        if not all(context.has_scope(scope) for scope in required_scopes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Required scope is missing",
            )
        return context

    return dependency


def get_admin_user_id(context: AuthContext = Depends(get_active_auth_context)) -> int:
    """Validate an administrator token and return its user identifier."""
    if not context.has_role(Role.SUPER_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return context.user_id


def verify_admin_token(token: str | None) -> int:
    """Validate an administrator token outside FastAPI dependency injection."""
    context = _context_from_claims(_decode_token(token, headers={"WWW-Authenticate": "Bearer"}))
    if not context.has_role(Role.SUPER_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return context.user_id
