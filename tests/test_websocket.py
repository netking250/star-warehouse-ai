import uuid
from contextlib import asynccontextmanager

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core import database
from app.core.config import settings
from app.core.redis import get_redis_client
from app.core.security import Role, create_access_token
from app.core.tenancy import TenantStatus, tenant_scope
from app.core.utils import build_thread_id
from app.main import app
from app.models.tenant import Tenant
from app.models.user import User
from app.websocket.manager import ConnectionManager


class FakeRedis:
    def __init__(self):
        self.values = {}

    async def mget(self, *keys):
        return [self.values.get(key) for key in keys]

    async def setex(self, key, ttl, value):
        self.values[key] = value


class TestBuildThreadId:
    def test_adds_user_prefix(self):
        assert build_thread_id(42, "thread-abc") == "default__42__thread-abc"

    def test_sanitizes_unsafe_characters(self):
        assert build_thread_id(1, "thread/abc@!") == "default__1__thread_abc__"

    def test_idempotent_when_already_prefixed(self):
        scoped = "default__99__existing"
        assert build_thread_id(99, scoped) == scoped

    def test_truncates_long_id(self):
        long_id = "x" * 200
        result = build_thread_id(1, long_id)
        assert len(result) <= 128
        assert result.startswith("default__1__")


class TestWebsocketSecurity:
    @pytest.fixture(autouse=True)
    def setup_client(self, monkeypatch):
        app.state.manager = ConnectionManager()
        redis = FakeRedis()
        app.state.redis_client = redis
        app.dependency_overrides[get_redis_client] = lambda: redis
        test_engine = create_async_engine(
            settings.DATABASE_URL,
            echo=False,
            poolclass=NullPool,
            connect_args={
                "timeout": settings.DB_CONNECT_TIMEOUT,
                "server_settings": {"application_name": settings.SERVICE_NAME, "jit": "off"},
            },
        )
        test_session_maker = async_sessionmaker(
            test_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        @asynccontextmanager
        async def _test_lifespan(_app):
            yield

        monkeypatch.setattr(database, "async_session_maker", test_session_maker)
        monkeypatch.setattr(app.router, "lifespan_context", _test_lifespan)

        with TestClient(app) as client:
            self.client = client
            try:
                yield
            finally:
                assert client.portal is not None
                client.portal.call(test_engine.dispose)
        app.dependency_overrides.pop(get_redis_client, None)

    def _create_user(
        self,
        role: Role = Role.CUSTOMER,
        tenant_id: str = settings.LOCAL_BOOTSTRAP_TENANT_ID,
    ) -> int:
        async def create() -> int:
            unique = uuid.uuid4().hex[:12]
            with tenant_scope(tenant_id):
                async with database.async_session_maker() as session, session.begin():
                    user = User(
                        tenant_id=tenant_id,
                        username=f"ws_{unique}",
                        password_hash=User.hash_password("websocket-password"),
                        email=f"ws_{unique}@example.com",
                        full_name="WebSocket User",
                        role=role.value,
                        is_admin=role is Role.SUPER_ADMIN,
                    )
                    session.add(user)
                    await session.flush()
                    if user.id is None:
                        raise RuntimeError("WebSocket test user ID was not assigned")
                    return user.id

        assert self.client.portal is not None
        return self.client.portal.call(create)

    def _create_tenant(self) -> str:
        async def create() -> str:
            tenant_id = f"ws-tenant-{uuid.uuid4().hex[:12]}"
            async with database.async_session_maker() as session, session.begin():
                session.add(
                    Tenant(
                        id=tenant_id,
                        slug=tenant_id,
                        display_name="WebSocket Tenant",
                        status=TenantStatus.ACTIVE,
                    )
                )
            return tenant_id

        assert self.client.portal is not None
        return self.client.portal.call(create)

    def test_connect_user_scopes_thread_id(self):
        """WebSocket endpoint 应通过 build_thread_id 限定 thread_id。"""
        user_id = self._create_user()
        token = create_access_token(user_id=user_id, is_admin=False)
        thread_id = "my-thread"
        expected_scoped = build_thread_id(user_id, thread_id)

        with self.client.websocket_connect(
            f"/api/v1/ws/{thread_id}",
            headers={
                "Origin": settings.CORS_ORIGINS[0],
                "Cookie": f"{settings.BROWSER_AUTH_COOKIE_NAME}={token}",
            },
        ):
            assert user_id in app.state.manager.active_connections
            assert expected_scoped in app.state.manager.active_connections[user_id]

    def test_user_b_cannot_access_user_a_scoped_thread(self):
        """验证用户B无法订阅或访问用户A的限定线程。"""
        user_a_id = self._create_user()
        user_b_id = self._create_user()
        token_a = create_access_token(user_id=user_a_id, is_admin=False)
        token_b = create_access_token(user_id=user_b_id, is_admin=False)
        thread_id = "shared-thread"

        with (
            self.client.websocket_connect(
                f"/api/v1/ws/{thread_id}",
                headers={
                    "Origin": settings.CORS_ORIGINS[0],
                    "Cookie": f"{settings.BROWSER_AUTH_COOKIE_NAME}={token_a}",
                },
            ),
            self.client.websocket_connect(
                f"/api/v1/ws/{thread_id}",
                headers={
                    "Origin": settings.CORS_ORIGINS[0],
                    "Cookie": f"{settings.BROWSER_AUTH_COOKIE_NAME}={token_b}",
                },
            ),
        ):
            scoped_a = build_thread_id(user_a_id, thread_id)
            scoped_b = build_thread_id(user_b_id, thread_id)

            assert scoped_a in app.state.manager.thread_subscribers
            assert scoped_b in app.state.manager.thread_subscribers
            assert (
                app.state.manager.thread_subscribers[scoped_a]
                != app.state.manager.thread_subscribers[scoped_b]
            )

    def test_invalid_token_does_not_leak_details(self):
        """无效 Token 时不应向客户端暴露内部错误详情。"""
        with (
            pytest.raises(WebSocketDisconnect) as exc_info,
            self.client.websocket_connect(
                "/api/v1/ws/some-thread?token=valid-looking"
            ) as websocket,
        ):
            websocket.receive_text()

        assert exc_info.value.code == 1008
        assert exc_info.value.reason == "Authentication failed"

    def test_admin_invalid_token_does_not_leak_details(self):
        """管理员端点无效 Token 时不应向客户端暴露内部错误详情。"""
        with (
            pytest.raises(WebSocketDisconnect) as exc_info,
            self.client.websocket_connect(
                "/api/v1/ws/admin/1",
                headers={
                    "Origin": settings.CORS_ORIGINS[0],
                    "Cookie": f"{settings.BROWSER_AUTH_COOKIE_NAME}=bad-token",
                },
            ) as websocket,
        ):
            websocket.receive_text()

        assert exc_info.value.code == 1008
        assert exc_info.value.reason == "Authentication failed"

    def test_admin_id_mismatch_does_not_leak_details(self):
        """管理员 ID 不匹配时不应向客户端暴露内部错误详情。"""
        admin_id = self._create_user(Role.SUPER_ADMIN)
        token = create_access_token(user_id=admin_id, is_admin=True)
        with (
            pytest.raises(WebSocketDisconnect) as exc_info,
            self.client.websocket_connect(
                "/api/v1/ws/admin/999",
                headers={
                    "Origin": settings.CORS_ORIGINS[0],
                    "Cookie": f"{settings.BROWSER_AUTH_COOKIE_NAME}={token}",
                },
            ) as websocket,
        ):
            websocket.receive_text()

        assert exc_info.value.code == 1008
        assert exc_info.value.reason == "Authentication failed"

    def test_revoked_token_cannot_open_websocket(self):
        user_id = self._create_user()
        token = create_access_token(user_id=user_id, is_admin=False)
        response = self.client.post("/api/v1/logout", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 204

        with (
            pytest.raises(WebSocketDisconnect) as exc_info,
            self.client.websocket_connect(
                "/api/v1/ws/revoked",
                headers={
                    "Origin": settings.CORS_ORIGINS[0],
                    "Cookie": f"{settings.BROWSER_AUTH_COOKIE_NAME}={token}",
                },
            ) as websocket,
        ):
            websocket.receive_text()

        assert exc_info.value.code == 1008

    def test_expired_cookie_cannot_open_websocket(self, monkeypatch):
        user_id = self._create_user()
        monkeypatch.setattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", -1)
        token = create_access_token(user_id=user_id, is_admin=False)

        with (
            pytest.raises(WebSocketDisconnect) as exc_info,
            self.client.websocket_connect(
                "/api/v1/ws/expired",
                headers={
                    "Origin": settings.CORS_ORIGINS[0],
                    "Cookie": f"{settings.BROWSER_AUTH_COOKIE_NAME}={token}",
                },
            ) as websocket,
        ):
            websocket.receive_text()

        assert exc_info.value.code == 1008

    def test_cookie_with_untrusted_origin_is_rejected(self):
        user_id = self._create_user()
        token = create_access_token(user_id=user_id, is_admin=False)

        with (
            pytest.raises(WebSocketDisconnect) as exc_info,
            self.client.websocket_connect(
                "/api/v1/ws/untrusted-origin",
                headers={
                    "Origin": "http://attacker.example",
                    "Cookie": f"{settings.BROWSER_AUTH_COOKIE_NAME}={token}",
                },
            ) as websocket,
        ):
            websocket.receive_text()

        assert exc_info.value.code == 1008

    def test_cookie_without_required_scope_is_rejected(self):
        user_id = self._create_user(Role.AUDITOR)
        token = create_access_token(user_id=user_id, roles=[Role.AUDITOR])

        with (
            pytest.raises(WebSocketDisconnect) as exc_info,
            self.client.websocket_connect(
                "/api/v1/ws/missing-scope",
                headers={
                    "Origin": settings.CORS_ORIGINS[0],
                    "Cookie": f"{settings.BROWSER_AUTH_COOKIE_NAME}={token}",
                },
            ) as websocket,
        ):
            websocket.receive_text()

        assert exc_info.value.code == 1008

    def test_tenant_a_cookie_cannot_authorize_tenant_b_admin_connection(self):
        tenant_b = self._create_tenant()
        tenant_a_admin = self._create_user(Role.SUPER_ADMIN)
        tenant_b_admin = self._create_user(Role.SUPER_ADMIN, tenant_b)
        token_a = create_access_token(user_id=tenant_a_admin, is_admin=True)

        with (
            pytest.raises(WebSocketDisconnect) as exc_info,
            self.client.websocket_connect(
                f"/api/v1/ws/admin/{tenant_b_admin}",
                headers={
                    "Origin": settings.CORS_ORIGINS[0],
                    "Cookie": f"{settings.BROWSER_AUTH_COOKIE_NAME}={token_a}",
                },
            ) as websocket,
        ):
            websocket.receive_text()

        assert exc_info.value.code == 1008
