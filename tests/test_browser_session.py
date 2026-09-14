"""Targeted T10 secure browser-session transport verification."""

import uuid
from collections.abc import Iterator

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.core.browser_session import origin_is_trusted, request_origin_is_trusted
from app.core.config import Settings, settings
from app.core.database import async_session_maker
from app.core.redis import get_redis_client
from app.core.security import Role, create_access_token
from app.main import app
from app.models.user import User


class FakeRedis:
    """Minimal revocation store used by browser-session transport tests."""

    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def mget(self, *keys: str) -> list[str | None]:
        return [self.values.get(key) for key in keys]

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.values[key] = value


def test_browser_cookie_defaults_are_production_safe_and_origin_matching_is_exact() -> None:
    """Secure and SameSite are explicit defaults; attacker suffixes do not match."""
    assert type(settings).model_fields["BROWSER_AUTH_COOKIE_SECURE"].default is True
    assert type(settings).model_fields["BROWSER_AUTH_COOKIE_SAMESITE"].default == "lax"
    trusted = settings.CORS_ORIGINS[0]
    assert origin_is_trusted(trusted)
    assert not origin_is_trusted(f"{trusted}.attacker.example")
    assert request_origin_is_trusted({"referer": f"{trusted}/authenticated/page"})
    assert not request_origin_is_trusted({"referer": f"{trusted}.attacker.example/page"})


def test_production_and_samesite_none_reject_insecure_cookie_configuration() -> None:
    """Explicit development overrides cannot silently weaken production or SameSite=None."""
    values = settings.model_dump()
    with pytest.raises(ValidationError, match="Production browser authentication cookies"):
        Settings.model_validate(
            {**values, "ENVIRONMENT": "production", "BROWSER_AUTH_COOKIE_SECURE": False}
        )
    with pytest.raises(ValidationError, match="SameSite=None browser authentication cookies"):
        Settings.model_validate(
            {
                **values,
                "ENVIRONMENT": "development",
                "BROWSER_AUTH_COOKIE_SECURE": False,
                "BROWSER_AUTH_COOKIE_SAMESITE": "none",
            }
        )


@pytest.fixture
def browser_redis() -> Iterator[FakeRedis]:
    redis = FakeRedis()
    app.dependency_overrides[get_redis_client] = lambda: redis
    try:
        yield redis
    finally:
        app.dependency_overrides.pop(get_redis_client, None)


async def _create_browser_user(role: Role = Role.CUSTOMER) -> tuple[User, str]:
    password = "browser-password"
    unique = uuid.uuid4().hex[:12]
    async with async_session_maker() as session:
        user = User(
            username=f"browser_{unique}",
            password_hash=User.hash_password(password),
            email=f"browser_{unique}@example.com",
            full_name="Browser Session User",
            is_active=True,
            role=role.value,
            is_admin=role is Role.SUPER_ADMIN,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user, password


@pytest.mark.asyncio
async def test_browser_login_sets_production_secure_httponly_host_only_cookie(client) -> None:
    """Browser login returns identity data and a production-safe host-only auth cookie."""
    user, password = await _create_browser_user()

    response = await client.post(
        "/api/v1/browser/login",
        json={"username": user.username, "password": password},
    )

    assert response.status_code == 200
    assert "access_token" not in response.json()
    set_cookie = response.headers["set-cookie"]
    assert set_cookie.startswith(f"{settings.BROWSER_AUTH_COOKIE_NAME}=")
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert "Path=/" in set_cookie
    assert "Domain=" not in set_cookie
    max_age = int(set_cookie.split("Max-Age=", 1)[1].split(";", 1)[0])
    assert 0 < max_age <= settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


@pytest.mark.asyncio
async def test_protected_browser_get_authenticates_with_cookie(
    client, monkeypatch, browser_redis
) -> None:
    """A browser can restore authoritative identity without reading the auth token."""
    monkeypatch.setattr(settings, "BROWSER_AUTH_COOKIE_SECURE", False)
    user, password = await _create_browser_user()
    login_response = await client.post(
        "/api/v1/browser/login",
        json={"username": user.username, "password": password},
    )
    assert login_response.status_code == 200

    response = await client.get("/api/v1/me")

    assert response.status_code == 200
    assert response.json()["user_id"] == user.id


@pytest.mark.asyncio
async def test_cookie_logout_requires_session_bound_csrf_and_trusted_origin(
    client, monkeypatch, browser_redis
) -> None:
    """Unsafe cookie-authenticated requests fail closed until both browser proofs are valid."""
    monkeypatch.setattr(settings, "BROWSER_AUTH_COOKIE_SECURE", False)
    user, password = await _create_browser_user()
    login_response = await client.post(
        "/api/v1/browser/login",
        json={"username": user.username, "password": password},
    )
    assert login_response.status_code == 200

    csrf_response = await client.get("/api/v1/browser/csrf")
    assert csrf_response.status_code == 200
    csrf_token = csrf_response.json()["csrf_token"]

    missing = await client.post("/api/v1/logout")
    invalid = await client.post(
        "/api/v1/logout",
        headers={"Origin": settings.CORS_ORIGINS[0], "X-CSRF-Token": "invalid"},
    )
    untrusted = await client.post(
        "/api/v1/logout",
        headers={"Origin": "http://attacker.example", "X-CSRF-Token": csrf_token},
    )

    assert missing.status_code == 403
    assert invalid.status_code == 403
    assert untrusted.status_code == 403


@pytest.mark.asyncio
async def test_csrf_token_cannot_cross_sessions_and_logout_revokes_stale_cookie(
    client, monkeypatch, browser_redis
) -> None:
    """Authentication rotation isolates CSRF state and logout revokes copied credentials."""
    monkeypatch.setattr(settings, "BROWSER_AUTH_COOKIE_SECURE", False)
    user_a, password_a = await _create_browser_user()
    user_b, password_b = await _create_browser_user()
    assert (
        await client.post(
            "/api/v1/browser/login",
            json={"username": user_a.username, "password": password_a},
        )
    ).status_code == 200
    cookie_a = client.cookies.get(settings.BROWSER_AUTH_COOKIE_NAME)
    csrf_a = (await client.get("/api/v1/browser/csrf")).json()["csrf_token"]

    assert (
        await client.post(
            "/api/v1/browser/login",
            json={"username": user_b.username, "password": password_b},
        )
    ).status_code == 200
    stale_cookie = client.cookies.get(settings.BROWSER_AUTH_COOKIE_NAME)
    client.cookies.set(settings.BROWSER_AUTH_COOKIE_NAME, cookie_a)
    assert (await client.get("/api/v1/me")).status_code == 401
    client.cookies.set(settings.BROWSER_AUTH_COOKIE_NAME, stale_cookie)
    cross_session = await client.post(
        "/api/v1/logout",
        headers={"Origin": settings.CORS_ORIGINS[0], "X-CSRF-Token": csrf_a},
    )
    assert cross_session.status_code == 403

    csrf_b = (await client.get("/api/v1/browser/csrf")).json()["csrf_token"]
    logout = await client.post(
        "/api/v1/logout",
        headers={"Origin": settings.CORS_ORIGINS[0], "X-CSRF-Token": csrf_b},
    )
    assert logout.status_code == 204
    assert "Max-Age=0" in logout.headers["set-cookie"]

    client.cookies.set(settings.BROWSER_AUTH_COOKIE_NAME, stale_cookie)
    assert (await client.get("/api/v1/me")).status_code == 401


@pytest.mark.asyncio
async def test_bearer_client_needs_no_csrf_and_ambiguous_credentials_cannot_bypass(
    client, monkeypatch, browser_redis
) -> None:
    """Bearer compatibility remains while any cookie ambiguity fails closed."""
    monkeypatch.setattr(settings, "BROWSER_AUTH_COOKIE_SECURE", False)
    user, password = await _create_browser_user()
    assert user.id is not None
    bearer_token = create_access_token(user.id, tenant_id=user.tenant_id)

    bearer_client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    try:
        bearer_logout = await bearer_client.post(
            "/api/v1/logout",
            headers={"Authorization": f"Bearer {bearer_token}"},
        )
    finally:
        await bearer_client.aclose()
    assert bearer_logout.status_code == 204

    browser_login = await client.post(
        "/api/v1/browser/login",
        json={"username": user.username, "password": password},
    )
    assert browser_login.status_code == 200
    cookie_token = client.cookies.get(settings.BROWSER_AUTH_COOKIE_NAME)
    same_credential = await client.post(
        "/api/v1/logout",
        headers={"Authorization": f"Bearer {cookie_token}"},
    )
    conflicting = await client.post(
        "/api/v1/logout",
        headers={"Authorization": f"Bearer {create_access_token(user.id)}"},
    )

    assert same_credential.status_code == 403
    assert conflicting.status_code == 401


@pytest.mark.asyncio
async def test_cookie_session_reflects_current_role_revocation_immediately(
    client, monkeypatch, browser_redis
) -> None:
    """Cookie transport does not turn JWT authorization snapshots into authority."""
    monkeypatch.setattr(settings, "BROWSER_AUTH_COOKIE_SECURE", False)
    user, password = await _create_browser_user(Role.IDENTITY_MANAGER)
    assert user.id is not None
    assert (
        await client.post(
            "/api/v1/browser/login",
            json={"username": user.username, "password": password},
        )
    ).status_code == 200
    assert (await client.get("/api/v1/admin/authorization/memberships")).status_code == 200

    async with async_session_maker() as session, session.begin():
        current_user = await session.get(User, user.id)
        assert current_user is not None
        current_user.role = Role.CUSTOMER.value
        current_user.is_admin = False
        session.add(current_user)

    denied = await client.get("/api/v1/admin/authorization/memberships")
    assert denied.status_code == 403
