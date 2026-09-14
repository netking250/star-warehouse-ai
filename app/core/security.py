"""JWT authentication and FastAPI adapters for the authorization policy seam."""

import logging
import secrets
from collections.abc import Callable, Iterable
from datetime import timedelta
from uuid import uuid4

import jwt
import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request, WebSocket, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field, ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.authorization.policy import (
    AuthenticatedPrincipal,
    AuthorizationContext,
    AuthorizationPolicy,
    AuthorizationReason,
    AuthorizationResolutionError,
    Role,
    Scope,
    authorize,
    resolve_authorization_context,
    scopes_for_roles,
)
from app.core.browser_session import (
    CSRF_HEADER_NAME,
    csrf_token_is_valid,
    request_origin_is_trusted,
)
from app.core.config import settings
from app.core.database import get_session
from app.core.logging import get_correlation_id
from app.core.redis import get_redis_client
from app.core.tenancy import namespaced_key, set_current_tenant_context, validate_tenant_id
from app.core.tenant_resolver import TenantResolver, tenant_id_from_request
from app.core.utils import utc_now

logger = logging.getLogger(__name__)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/login", auto_error=False)

# Compatibility export for existing route annotations. The authoritative definition lives in
# app.authorization.policy.
AuthContext = AuthorizationContext


class _TokenClaims(BaseModel):
    """Validated access-token claims."""

    sub: str
    exp: int
    iat: int
    iss: str
    aud: str | list[str]
    jti: str
    tenant_id: str
    roles: list[str] = Field(min_length=1)
    scopes: list[str]
    session_id: str
    is_admin: bool = False


def extract_bearer_token(auth_header: str) -> str | None:
    """Extract a bearer token from an Authorization header."""
    if auth_header.lower().startswith("bearer ") and len(auth_header) > 7:
        return auth_header[7:]
    return None


def _normalize_roles(roles: Iterable[Role | str]) -> frozenset[Role]:
    normalized = frozenset(Role(role) for role in roles)
    if not normalized:
        raise ValueError("At least one role is required")
    return normalized


def create_access_token(
    user_id: int,
    is_admin: bool = False,
    *,
    tenant_id: str | None = None,
    roles: Iterable[Role | str] | None = None,
    scopes: Iterable[str] | None = None,
    session_id: str | None = None,
) -> str:
    """Create a signed application access token.

    Role and scope claims remain a compatibility snapshot for clients. Protected requests resolve
    current local tenant membership and role state before evaluating policy.

    Args:
        user_id: Stable local user identifier.
        is_admin: Backward-compatible application administrator flag.
        tenant_id: Tenant namespace asserted by the authenticated login flow.
        roles: Compatibility role snapshot. Defaults from ``is_admin``.
        scopes: Compatibility scope snapshot. Defaults from ``roles``.
        session_id: Login session identifier. A random identifier is generated when omitted.

    Returns:
        Encoded JWT access token.
    """
    validated_tenant_id = tenant_id_from_request(tenant_id)
    normalized_roles = _normalize_roles(
        roles if roles is not None else [Role.SUPER_ADMIN if is_admin else Role.CUSTOMER]
    )
    normalized_scopes = (
        frozenset(scopes) if scopes is not None else scopes_for_roles(normalized_roles)
    )
    now = utc_now()
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token_id = str(uuid4())
    payload = {
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
    return jwt.encode(payload, settings.SECRET_KEY.get_secret_value(), algorithm=settings.ALGORITHM)


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
        validate_tenant_id(claims.tenant_id)
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


def _principal_from_claims(claims: _TokenClaims) -> AuthenticatedPrincipal:
    try:
        user_id = int(claims.sub)
    except (ValueError, TypeError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: malformed user ID",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
    return AuthenticatedPrincipal(
        tenant_id=claims.tenant_id,
        user_id=user_id,
        session_id=claims.session_id,
        correlation_id=get_correlation_id(),
        token_id=claims.jti,
        expires_at=claims.exp,
        token_roles=frozenset(claims.roles),
        token_scopes=frozenset(claims.scopes),
    )


async def _ensure_principal_is_active(
    principal: AuthenticatedPrincipal, redis: aioredis.Redis
) -> AuthenticatedPrincipal:
    """Reject a token or login session that has been revoked."""
    try:
        revoked = await redis.mget(
            namespaced_key(f"auth:revoked:token:{principal.token_id}", principal.tenant_id),
            namespaced_key(f"auth:revoked:session:{principal.session_id}", principal.tenant_id),
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
    return principal


async def revoke_auth_context(
    context: AuthenticatedPrincipal | AuthorizationContext, redis: aioredis.Redis
) -> None:
    """Revoke the current token until its original expiry time."""
    ttl = max(1, context.expires_at - int(utc_now().timestamp()))
    await redis.setex(
        namespaced_key(f"auth:revoked:token:{context.token_id}", context.tenant_id),
        ttl,
        "1",
    )


def get_auth_context(
    token: str | None = Depends(oauth2_scheme),
) -> AuthenticatedPrincipal:
    """Validate the bearer token and return an authority-free principal."""
    claims = _decode_token(
        token,
        headers={"WWW-Authenticate": "Bearer"},
        missing_user_detail="Invalid token: missing user ID",
    )
    return _principal_from_claims(claims)


def get_request_auth_context(
    request: Request,
    bearer_token: str | None = Depends(oauth2_scheme),
) -> AuthenticatedPrincipal:
    """Normalize Bearer or browser-cookie authentication into one principal.

    Cookie authentication remains subject to browser CSRF and Origin controls for unsafe methods.
    If the same credential is supplied through both transports it is treated as cookie auth; two
    different credentials are rejected rather than relying on precedence.
    """
    cookie_token = request.cookies.get(settings.BROWSER_AUTH_COOKIE_NAME)
    uses_cookie = cookie_token is not None
    if bearer_token is not None and cookie_token is not None:
        if not secrets.compare_digest(bearer_token, cookie_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Conflicting authentication credentials",
            )
        token = cookie_token
    else:
        token = cookie_token or bearer_token

    principal = get_auth_context(token)
    if uses_cookie and request.method.upper() not in {"GET", "HEAD", "OPTIONS", "TRACE"}:
        if not request_origin_is_trusted(request.headers):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Browser request validation failed",
            )
        if not csrf_token_is_valid(request.headers.get(CSRF_HEADER_NAME), principal):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Browser request validation failed",
            )
    return principal


def get_websocket_auth_token(websocket: WebSocket) -> str:
    """Resolve header or cookie WebSocket auth while forbidding URL credentials."""
    if "token" in websocket.query_params or "access_token" in websocket.query_params:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="WebSocket query credentials are not accepted",
        )
    bearer_token = extract_bearer_token(websocket.headers.get("authorization", ""))
    cookie_token = websocket.cookies.get(settings.BROWSER_AUTH_COOKIE_NAME)
    if bearer_token is not None and cookie_token is not None:
        if not secrets.compare_digest(bearer_token, cookie_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Conflicting authentication credentials",
            )
        token = cookie_token
    else:
        token = cookie_token or bearer_token
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
        )
    if cookie_token is not None and not request_origin_is_trusted(websocket.headers):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Browser request validation failed",
        )
    return token


def _log_authorization_denial(
    *,
    principal: AuthenticatedPrincipal,
    policy: AuthorizationPolicy | None,
    reason: AuthorizationReason,
) -> None:
    logger.warning(
        "Authorization denied",
        extra={
            "event_code": "authorization.denied",
            "actor_user_id": principal.user_id,
            "tenant_id": principal.tenant_id,
            "policy_scopes": sorted(scope.value for scope in policy.scopes) if policy else [],
            "policy_roles": sorted(role.value for role in policy.roles) if policy else [],
            "decision": "DENY",
            "reason_code": reason.value,
            "correlation_id": principal.correlation_id,
        },
    )


async def get_active_auth_context(
    principal: AuthenticatedPrincipal = Depends(get_request_auth_context),
    redis: aioredis.Redis = Depends(get_redis_client),
    session: AsyncSession = Depends(get_session),
) -> AuthorizationContext:
    """Resolve current local membership and authority after authentication."""
    active_principal = await _ensure_principal_is_active(principal, redis)
    tenant_context = await TenantResolver(session).resolve(active_principal.tenant_id)
    set_current_tenant_context(tenant_context)
    try:
        return await resolve_authorization_context(session, active_principal, tenant_context)
    except AuthorizationResolutionError as error:
        _log_authorization_denial(
            principal=active_principal,
            policy=None,
            reason=error.reason,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access is not permitted",
        ) from error


def _enforce_policy(
    context: AuthorizationContext, policy: AuthorizationPolicy
) -> AuthorizationContext:
    decision = authorize(context, policy)
    if decision.allowed:
        return context
    _log_authorization_denial(
        principal=context.principal,
        policy=policy,
        reason=decision.reason,
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access is not permitted",
    )


def _request_route_policy(request: Request) -> AuthorizationPolicy:
    from app.authorization.route_inventory import policy_for_http_route

    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    route_policy = (
        policy_for_http_route(request.method, route_path) if isinstance(route_path, str) else None
    )
    if route_policy is None or route_policy.authorization is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access is not permitted",
        )
    return route_policy.authorization


def get_authorized_auth_context(
    request: Request,
    context: AuthorizationContext = Depends(get_active_auth_context),
) -> AuthorizationContext:
    """Enforce the current route's centrally declared capability policy."""
    return _enforce_policy(context, _request_route_policy(request))


def get_current_user_id(token: str | None = Depends(oauth2_scheme)) -> int:
    """Validate the bearer token and return its local identity ID."""
    return get_auth_context(token).user_id


def get_active_user_id(
    context: AuthorizationContext = Depends(get_active_auth_context),
) -> int:
    """Return the user ID after membership and account-state validation."""
    return context.user_id


def get_authorized_user_id(
    context: AuthorizationContext = Depends(get_authorized_auth_context),
) -> int:
    """Return the user ID after enforcing the registered route policy."""
    return context.user_id


async def _get_authorized_context_ws(
    token: str,
    redis: aioredis.Redis,
    *,
    route_path: str,
) -> AuthorizationContext:
    from app.authorization.route_inventory import policy_for_websocket_route
    from app.core.database import async_session_maker

    principal = await _ensure_principal_is_active(
        _principal_from_claims(_decode_token(token)), redis
    )
    async with async_session_maker() as session:
        tenant_context = await TenantResolver(session).resolve(principal.tenant_id)
        set_current_tenant_context(tenant_context)
        try:
            context = await resolve_authorization_context(session, principal, tenant_context)
        except AuthorizationResolutionError as error:
            _log_authorization_denial(principal=principal, policy=None, reason=error.reason)
            raise HTTPException(status_code=403, detail="Access is not permitted") from error

    route_policy = policy_for_websocket_route(route_path)
    if route_policy is None or route_policy.authorization is None:
        raise HTTPException(status_code=403, detail="Access is not permitted")
    return _enforce_policy(context, route_policy.authorization)


async def get_current_user_id_ws(token: str, redis: aioredis.Redis) -> int:
    """Authorize a tenant chat WebSocket and return its current user ID."""
    context = await _get_authorized_context_ws(token, redis, route_path="/api/v1/ws/{thread_id}")
    return context.user_id


async def get_admin_user_id_ws(token: str, redis: aioredis.Redis) -> int:
    """Authorize an operations-read WebSocket and return its current user ID."""
    context = await _get_authorized_context_ws(
        token, redis, route_path="/api/v1/ws/admin/{admin_id}"
    )
    return context.user_id


def require_roles(
    *allowed_roles: Role,
) -> Callable[[AuthorizationContext], AuthorizationContext]:
    """Create a dependency requiring one of the current local application roles."""
    if not allowed_roles:
        raise ValueError("At least one allowed role is required")
    policy = AuthorizationPolicy(roles=frozenset(allowed_roles))

    def dependency(
        context: AuthorizationContext = Depends(get_active_auth_context),
    ) -> AuthorizationContext:
        return _enforce_policy(context, policy)

    return dependency


def require_scopes(
    *required_scopes: Scope | str,
) -> Callable[[AuthorizationContext], AuthorizationContext]:
    """Create a dependency requiring every listed canonical capability."""
    if not required_scopes:
        raise ValueError("At least one required scope is required")
    try:
        policy = AuthorizationPolicy(scopes=frozenset(Scope(scope) for scope in required_scopes))
    except ValueError as error:
        raise ValueError("Required scopes must use the canonical dotted vocabulary") from error

    def dependency(
        context: AuthorizationContext = Depends(get_active_auth_context),
    ) -> AuthorizationContext:
        return _enforce_policy(context, policy)

    return dependency


def get_admin_user_id(
    context: AuthorizationContext = Depends(get_authorized_auth_context),
) -> int:
    """Return the actor ID after the admin route's explicit capability policy passes."""
    return context.user_id
