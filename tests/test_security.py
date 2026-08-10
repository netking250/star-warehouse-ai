from datetime import timedelta
from unittest.mock import AsyncMock

import jwt
import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.core.security import (
    AuthContext,
    Role,
    create_access_token,
    get_active_auth_context,
    get_auth_context,
    get_current_user_id,
    require_roles,
    require_scopes,
    revoke_auth_context,
    verify_admin_token,
)
from app.core.utils import utc_now


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


class TestVerifyAdminToken:
    def test_returns_user_id_for_admin_token(self):
        token = create_access_token(user_id=7, is_admin=True)
        user_id = verify_admin_token(token)
        assert user_id == 7

    def test_raises_403_for_non_admin_token(self):
        token = create_access_token(user_id=7, is_admin=False)
        with pytest.raises(HTTPException) as exc_info:
            verify_admin_token(token)
        assert exc_info.value.status_code == 403
        assert "Admin privileges required" in exc_info.value.detail

    def test_raises_401_for_invalid_token(self):
        with pytest.raises(HTTPException) as exc_info:
            verify_admin_token("invalid-token")
        assert exc_info.value.status_code == 401
        assert "Invalid token" in exc_info.value.detail


class TestAuthContext:
    def test_builds_tenant_role_scope_and_session_context(self):
        token = create_access_token(
            user_id=91,
            tenant_id="tenant-acme",
            roles=[Role.REVIEWER],
            scopes=["review:read", "review:decide"],
            session_id="session-123",
        )

        context = get_auth_context(token)

        assert context == AuthContext(
            tenant_id="tenant-acme",
            user_id=91,
            roles=frozenset({Role.REVIEWER}),
            scopes=frozenset({"review:read", "review:decide"}),
            session_id="session-123",
            correlation_id="-",
            token_id=context.token_id,
        )
        assert context.has_role(Role.REVIEWER)
        assert context.has_scope("review:decide")

    def test_rejects_invalid_tenant_claim(self):
        with pytest.raises(ValueError, match="tenant_id"):
            create_access_token(user_id=91, tenant_id="../../other-tenant")

    def test_role_dependency_denies_unlisted_role(self):
        context = AuthContext(
            tenant_id="tenant-acme",
            user_id=91,
            roles=frozenset({Role.ANALYST}),
            scopes=frozenset({"analytics:read"}),
            session_id="session-123",
            correlation_id="correlation-123",
            token_id="token-123",
        )

        with pytest.raises(HTTPException) as exc_info:
            require_roles(Role.REVIEWER)(context)

        assert exc_info.value.status_code == 403

    def test_scope_dependency_accepts_super_admin_wildcard(self):
        context = AuthContext(
            tenant_id="default",
            user_id=1,
            roles=frozenset({Role.SUPER_ADMIN}),
            scopes=frozenset({"*"}),
            session_id="session-123",
            correlation_id="correlation-123",
            token_id="token-123",
        )

        assert require_scopes("knowledge:publish")(context) is context


@pytest.mark.asyncio
async def test_revoked_token_is_rejected_immediately() -> None:
    context = get_auth_context(
        create_access_token(user_id=42, tenant_id="tenant-blue", session_id="session-blue")
    )
    redis = AsyncMock()
    redis.mget.side_effect = [[None, None], ["1", None]]

    assert await get_active_auth_context(context, redis) is context
    await revoke_auth_context(context, redis)
    with pytest.raises(HTTPException, match="revoked") as exc_info:
        await get_active_auth_context(context, redis)

    assert exc_info.value.status_code == 401
    revoked_key = redis.setex.await_args.args[0]
    assert revoked_key.endswith(f":tenant-blue:auth:revoked:token:{context.token_id}")
