from datetime import timedelta
from unittest.mock import AsyncMock

import jwt
import pytest
from fastapi import HTTPException

from app.authorization.policy import AuthenticatedPrincipal, AuthorizationContext, Role, Scope
from app.core.config import settings
from app.core.security import (
    create_access_token,
    get_active_auth_context,
    get_auth_context,
    get_current_user_id,
    require_roles,
    require_scopes,
    revoke_auth_context,
)
from app.core.tenancy import TenantContext, TenantStatus
from app.core.utils import utc_now
from app.models.user import User


def _authorization_context(
    *,
    tenant_id: str = "tenant-acme",
    user_id: int = 91,
    roles: frozenset[Role],
    scopes: frozenset[str],
) -> AuthorizationContext:
    return AuthorizationContext(
        principal=AuthenticatedPrincipal(
            tenant_id=tenant_id,
            user_id=user_id,
            session_id="session-123",
            correlation_id="correlation-123",
            token_id="token-123",
        ),
        tenant=TenantContext(
            tenant_id=tenant_id,
            slug=tenant_id,
            display_name="Security Test Tenant",
            status=TenantStatus.ACTIVE,
        ),
        roles=roles,
        scopes=scopes,
    )


class TestCreateAccessToken:
    def test_generates_valid_jwt_with_correct_claims(self):
        token = create_access_token(user_id=42, is_admin=True)
        payload = jwt.decode(
            token,
            settings.SECRET_KEY.get_secret_value(),
            algorithms=[settings.ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
        )

        assert payload["sub"] == "42"
        assert payload["is_admin"] is True
        assert payload["tenant_id"] == "default"
        assert payload["roles"] == ["super_admin"]
        assert payload["scopes"] == ["*"]
        assert payload["iss"] == settings.JWT_ISSUER
        assert payload["aud"] == settings.JWT_AUDIENCE
        assert payload["session_id"]
        assert payload["jti"]
        assert "exp" in payload
        assert "iat" in payload

        expected_expire = utc_now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        assert abs(payload["exp"] - expected_expire.timestamp()) < 5
        assert abs(payload["iat"] - utc_now().timestamp()) < 5


class TestGetCurrentUserId:
    def test_extracts_user_id_from_valid_token(self):
        token = create_access_token(user_id=123, is_admin=False)
        user_id = get_current_user_id(token)
        assert user_id == 123

    def test_raises_401_for_missing_token(self):
        with pytest.raises(HTTPException) as exc_info:
            get_current_user_id("")
        assert exc_info.value.status_code == 401
        assert "Missing authentication token" in exc_info.value.detail

    def test_raises_401_for_expired_token(self):
        expired_time = utc_now() - timedelta(minutes=1)
        payload = {
            "sub": "1",
            "exp": expired_time,
            "iat": utc_now() - timedelta(hours=2),
            "is_admin": False,
            "tenant_id": "default",
            "roles": ["customer"],
            "scopes": ["chat:use"],
            "session_id": "expired-session",
            "jti": "expired-token",
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
        }
        token = jwt.encode(
            payload, settings.SECRET_KEY.get_secret_value(), algorithm=settings.ALGORITHM
        )

        with pytest.raises(HTTPException) as exc_info:
            get_current_user_id(token)
        assert exc_info.value.status_code == 401
        assert "Token has expired" in exc_info.value.detail

    def test_raises_401_for_invalid_signature(self):
        token = jwt.encode({"sub": "1"}, "wrong-secret", algorithm=settings.ALGORITHM)
        with pytest.raises(HTTPException) as exc_info:
            get_current_user_id(token)
        assert exc_info.value.status_code == 401
        assert "Invalid token" in exc_info.value.detail

    def test_raises_401_for_malformed_token(self):
        with pytest.raises(HTTPException) as exc_info:
            get_current_user_id("not.a.token")
        assert exc_info.value.status_code == 401
        assert "Invalid token" in exc_info.value.detail

    def test_raises_401_for_wrong_audience(self):
        now = utc_now()
        token = jwt.encode(
            {
                "sub": "1",
                "exp": now + timedelta(minutes=5),
                "iat": now,
                "iss": settings.JWT_ISSUER,
                "aud": "another-api",
                "jti": "wrong-audience-token",
                "tenant_id": "default",
                "roles": ["customer"],
                "scopes": ["chat:use"],
                "session_id": "wrong-audience-session",
            },
            settings.SECRET_KEY.get_secret_value(),
            algorithm=settings.ALGORITHM,
        )

        with pytest.raises(HTTPException) as exc_info:
            get_current_user_id(token)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid token"

    def test_raises_401_for_missing_sub_claim(self):
        token = jwt.encode(
            {
                "exp": utc_now() + timedelta(hours=1),
                "iat": utc_now(),
                "is_admin": False,
                "tenant_id": "default",
                "roles": ["customer"],
                "scopes": ["chat:use"],
                "session_id": "missing-user-session",
                "jti": "missing-user-token",
                "iss": settings.JWT_ISSUER,
                "aud": settings.JWT_AUDIENCE,
            },
            settings.SECRET_KEY.get_secret_value(),
            algorithm=settings.ALGORITHM,
        )
        with pytest.raises(HTTPException) as exc_info:
            get_current_user_id(token)
        assert exc_info.value.status_code == 401
        assert "missing user ID" in exc_info.value.detail


class TestAuthenticatedPrincipal:
    def test_builds_authority_free_principal_with_compatibility_snapshots(self):
        token = create_access_token(
            user_id=91,
            tenant_id="tenant-acme",
            roles=[Role.REVIEWER],
            scopes=["review:read", "review:decide"],
            session_id="session-123",
        )

        principal = get_auth_context(token)

        assert principal == AuthenticatedPrincipal(
            tenant_id="tenant-acme",
            user_id=91,
            session_id="session-123",
            correlation_id="-",
            token_id=principal.token_id,
            token_roles=frozenset({Role.REVIEWER.value}),
            token_scopes=frozenset({"review:read", "review:decide"}),
        )

    def test_rejects_invalid_tenant_claim(self):
        with pytest.raises(ValueError, match="tenant_id"):
            create_access_token(user_id=91, tenant_id="../../other-tenant")

    def test_role_dependency_denies_unlisted_role(self):
        context = _authorization_context(
            roles=frozenset({Role.ANALYST}),
            scopes=frozenset({Scope.OPERATIONS_READ.value}),
        )

        with pytest.raises(HTTPException) as exc_info:
            require_roles(Role.REVIEWER)(context)

        assert exc_info.value.status_code == 403

    def test_scope_dependency_accepts_super_admin_wildcard(self):
        context = _authorization_context(
            tenant_id="default",
            user_id=1,
            roles=frozenset({Role.SUPER_ADMIN}),
            scopes=frozenset({"*"}),
        )

        assert require_scopes(Scope.KNOWLEDGE_WRITE)(context) is context


@pytest.mark.asyncio
async def test_revoked_token_is_rejected_immediately(db_session, tenant_context: str) -> None:
    user = User(
        tenant_id=tenant_context,
        username="security-revocation-user",
        password_hash=User.hash_password("security-password"),
        email="security-revocation@example.com",
        full_name="Security Revocation User",
        role=Role.CUSTOMER.value,
    )
    db_session.add(user)
    await db_session.flush()
    assert user.id is not None
    principal = get_auth_context(
        create_access_token(user_id=user.id, tenant_id=tenant_context, session_id="session-blue")
    )
    redis = AsyncMock()
    redis.mget.side_effect = [[None, None], ["1", None]]

    context = await get_active_auth_context(principal, redis, db_session)
    assert context.user_id == user.id
    await revoke_auth_context(context, redis)
    with pytest.raises(HTTPException, match="revoked") as exc_info:
        await get_active_auth_context(principal, redis, db_session)

    assert exc_info.value.status_code == 401
    revoked_key = redis.setex.await_args.args[0]
    assert revoked_key.endswith(f":{tenant_context}:auth:revoked:token:{context.token_id}")
