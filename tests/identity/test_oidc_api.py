"""OIDC API boundary tests for explicit tenancy and application-token compatibility."""

import uuid

import pytest
import redis.asyncio as aioredis

from app.api.v1.auth import get_oidc_provider_dependency
from app.core.config import settings
from app.core.database import async_session_maker
from app.main import app
from app.models.user import User
from app.services.identity_provider import ExternalIdentity, IdentityProviderError

ISSUER = "https://idp.example.com/realms/enterprise"


class StubOIDCProvider:
    """Deterministic provider after the cryptographic adapter boundary."""

    def __init__(
        self, *, fail_callback: bool = False, email: str = "api-person@example.com"
    ) -> None:
        self.fail_callback = fail_callback
        self.email = email

    async def start_authorization(self, redis: aioredis.Redis, tenant_id: str) -> str:
        return f"https://idp.example.com/auth?tenant_marker={tenant_id}"

    async def authenticate_callback(
        self, redis: aioredis.Redis, *, state: str, code: str
    ) -> tuple[ExternalIdentity, str]:
        if self.fail_callback:
            raise IdentityProviderError("oidc_state_invalid")
        return (
            ExternalIdentity(
                provider="enterprise-oidc",
                issuer=ISSUER,
                subject=f"employee-{self.email}",
                email=self.email,
                email_verified=True,
            ),
            "default",
        )


@pytest.mark.asyncio
async def test_oidc_login_requires_explicit_tenant_context(client) -> None:
    app.dependency_overrides[get_oidc_provider_dependency] = StubOIDCProvider
    try:
        response = await client.get("/api/v1/oidc/login", follow_redirects=False)
    finally:
        app.dependency_overrides.pop(get_oidc_provider_dependency, None)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_oidc_callback_sets_browser_cookie_without_exposing_application_token(
    client, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "OIDC_ISSUER", ISSUER)
    monkeypatch.setattr(settings, "OIDC_LINK_VERIFIED_EMAIL", True)
    unique = uuid.uuid4().hex[:10]
    email = f"api-person-{unique}@example.com"
    async with async_session_maker() as session, session.begin():
        user = User(
            username=f"oidc_api_{unique}",
            password_hash=User.hash_password("local-password"),
            email=email,
            full_name="API OIDC User",
            is_active=True,
        )
        session.add(user)

    app.dependency_overrides[get_oidc_provider_dependency] = lambda: StubOIDCProvider(email=email)
    try:
        response = await client.get(
            "/api/v1/oidc/callback",
            params={"state": "valid-state-value-123", "code": "valid-code"},
        )
    finally:
        app.dependency_overrides.pop(get_oidc_provider_dependency, None)

    assert response.status_code == 303
    assert response.headers["location"] == settings.BROWSER_POST_LOGIN_REDIRECT_PATH
    assert "access_token" not in response.headers["location"]
    assert "#" not in response.headers["location"]
    set_cookie = response.headers["set-cookie"]
    assert set_cookie.startswith(f"{settings.BROWSER_AUTH_COOKIE_NAME}=")
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie


@pytest.mark.asyncio
async def test_oidc_callback_exposes_stable_error_without_crypto_details(client) -> None:
    app.dependency_overrides[get_oidc_provider_dependency] = lambda: StubOIDCProvider(
        fail_callback=True
    )
    try:
        response = await client.get(
            "/api/v1/oidc/callback",
            params={"state": "invalid-state-value", "code": "forged-code"},
        )
    finally:
        app.dependency_overrides.pop(get_oidc_provider_dependency, None)

    assert response.status_code == 401
    assert response.json() == {"detail": "Enterprise identity authentication failed"}
