import uuid

import pytest
from fastapi import HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.database import async_session_maker
from app.core.security import create_access_token
from app.main import app
from app.models.user import User
from app.services.auth_service import AuthService


class FailingAfterCreateAuthService(AuthService):
    """Inject a failure after registration has staged its database write."""

    async def register_user(
        self,
        session: AsyncSession,
        username: str,
        password: str,
        email: str,
        full_name: str,
        phone: str | None = None,
    ) -> User:
        await super().register_user(
            session,
            username=username,
            password=password,
            email=email,
            full_name=full_name,
            phone=phone,
        )
        raise HTTPException(status_code=503, detail="forced registration failure")


@pytest.mark.asyncio
async def test_login_success_returns_token_response(client):
    unique = uuid.uuid4().hex[:8]
    username = f"login_ok_{unique}"
    password = "password123"

    async with async_session_maker() as session:
        user = User(
            username=username,
            password_hash=User.hash_password(password),
            email=f"{username}@test.com",
            full_name="Test User",
            is_admin=False,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        assert user.id is not None
        user_id = user.id

    response = await client.post(
        "/api/v1/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user_id"] == user_id
    assert data["username"] == username
    assert data["is_admin"] is False
    assert data["tenant_id"] == "default"
    assert data["roles"] == ["customer"]
    assert "chat:use" in data["scopes"]
    assert data["session_id"]


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client):
    unique = uuid.uuid4().hex[:8]
    username = f"login_wrong_{unique}"

    async with async_session_maker() as session:
        user = User(
            username=username,
            password_hash=User.hash_password("correctpass"),
            email=f"{username}@test.com",
            full_name="Test User",
            is_admin=False,
            is_active=True,
        )
        session.add(user)
        await session.commit()

    response = await client.post(
        "/api/v1/login",
        json={"username": username, "password": "wrongpass"},
    )
    assert response.status_code == 401
    assert "用户名或密码错误" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_nonexistent_user_returns_401(client):
    response = await client.post(
        "/api/v1/login",
        json={"username": "nonexistent_user_xyz", "password": "anypass"},
    )
    assert response.status_code == 401
    assert "用户名或密码错误" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_disabled_user_returns_403(client):
    unique = uuid.uuid4().hex[:8]
    username = f"login_disabled_{unique}"

    async with async_session_maker() as session:
        user = User(
            username=username,
            password_hash=User.hash_password("password123"),
            email=f"{username}@test.com",
            full_name="Test User",
            is_admin=False,
            is_active=False,
        )
        session.add(user)
        await session.commit()

    response = await client.post(
        "/api/v1/login",
        json={"username": username, "password": "password123"},
    )
    assert response.status_code == 403
    assert "账号已被禁用" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_success_creates_user_and_returns_token(client):
    unique = uuid.uuid4().hex[:8]
    username = f"register_ok_{unique}"

    response = await client.post(
        "/api/v1/register",
        json={
            "username": username,
            "password": "password123",
            "email": f"{username}@test.com",
            "full_name": "New User",
            "phone": "13800138000",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["username"] == username
    assert data["is_admin"] is False
    assert data["tenant_id"] == "default"
    assert data["roles"] == ["customer"]

    async with async_session_maker() as session:
        result = await session.exec(select(User).where(User.username == username))
        user = result.one_or_none()
        assert user is not None
        assert user.email == f"{username}@test.com"
        assert user.phone == "13800138000"


@pytest.mark.asyncio
async def test_register_failure_after_create_rolls_back_user(client):
    unique = uuid.uuid4().hex[:8]
    username = f"register_rollback_{unique}"
    app.dependency_overrides[AuthService] = FailingAfterCreateAuthService

    try:
        response = await client.post(
            "/api/v1/register",
            json={
                "username": username,
                "password": "password123",
                "email": f"{username}@test.com",
                "full_name": "Rollback User",
            },
        )
    finally:
        app.dependency_overrides.pop(AuthService, None)

    assert response.status_code == 503
    assert response.json()["detail"] == "forced registration failure"

    async with async_session_maker() as session:
        result = await session.exec(select(User).where(User.username == username))
        assert result.one_or_none() is None


@pytest.mark.asyncio
async def test_register_duplicate_username_returns_400(client):
    unique = uuid.uuid4().hex[:8]
    username = f"register_dup_user_{unique}"

    async with async_session_maker() as session:
        user = User(
            username=username,
            password_hash=User.hash_password("password123"),
            email=f"{username}_first@test.com",
            full_name="First User",
            is_admin=False,
            is_active=True,
        )
        session.add(user)
        await session.commit()

    response = await client.post(
        "/api/v1/register",
        json={
            "username": username,
            "password": "password123",
            "email": f"{username}_second@test.com",
            "full_name": "Second User",
        },
    )
    assert response.status_code == 400
    assert "用户名已存在" in response.json()["detail"]

    async with async_session_maker() as session:
        result = await session.exec(select(User).where(User.username == username))
        users = result.all()
        assert len(users) == 1
        assert users[0].email == f"{username}_first@test.com"


@pytest.mark.asyncio
async def test_register_unknown_tenant_fails_closed_without_creating_user(client):
    unique = uuid.uuid4().hex[:8]
    username = f"register_unknown_tenant_{unique}"

    response = await client.post(
        "/api/v1/register",
        json={
            "username": username,
            "password": "password123",
            "email": f"{username}@test.com",
            "full_name": "Unknown Tenant User",
            "tenant_id": f"tenant-unknown-{unique}",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "tenant_unknown"

    async with async_session_maker() as session:
        result = await session.exec(select(User).where(User.username == username))
        assert result.one_or_none() is None


@pytest.mark.asyncio
async def test_register_missing_tenant_in_production_fails_closed_without_creating_user(
    client, monkeypatch
):
    unique = uuid.uuid4().hex[:8]
    username = f"register_missing_tenant_{unique}"
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    response = await client.post(
        "/api/v1/register",
        json={
            "username": username,
            "password": "password123",
            "email": f"{username}@test.com",
            "full_name": "Missing Tenant User",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "tenant_missing"

    async with async_session_maker() as session:
        result = await session.exec(select(User).where(User.username == username))
        assert result.one_or_none() is None


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_400(client):
    unique = uuid.uuid4().hex[:8]
    email = f"register_dup_email_{unique}@test.com"

    async with async_session_maker() as session:
        user = User(
            username=f"first_user_{unique}",
            password_hash=User.hash_password("password123"),
            email=email,
            full_name="First User",
            is_admin=False,
            is_active=True,
        )
        session.add(user)
        await session.commit()

    response = await client.post(
        "/api/v1/register",
        json={
            "username": f"second_user_{unique}",
            "password": "password123",
            "email": email,
            "full_name": "Second User",
        },
    )
    assert response.status_code == 400
    assert "邮箱已被注册" in response.json()["detail"]


@pytest.mark.asyncio
async def test_me_valid_token_returns_user_info(client):
    unique = uuid.uuid4().hex[:8]
    username = f"me_ok_{unique}"

    async with async_session_maker() as session:
        user = User(
            username=username,
            password_hash=User.hash_password("password123"),
            email=f"{username}@test.com",
            full_name="Me Test",
            phone="13900139000",
            is_admin=False,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        assert user.id is not None
        token = create_access_token(user_id=user.id, is_admin=False)

    response = await client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == username
    assert data["email"] == f"{username}@test.com"
    assert data["full_name"] == "Me Test"
    assert data["phone"] == "13900139000"
    assert data["is_admin"] is False
    assert data["tenant_id"] == "default"
    assert data["roles"] == ["customer"]
    assert "chat:use" in data["scopes"]


@pytest.mark.asyncio
async def test_me_missing_token_returns_401(client):
    response = await client.get("/api/v1/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_invalid_token_returns_401(client):
    response = await client.get(
        "/api/v1/me",
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert response.status_code == 401
