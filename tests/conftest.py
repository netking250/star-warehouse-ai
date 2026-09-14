# ruff: noqa: I001

import uuid
from collections.abc import AsyncIterator, Iterator

import tests._db_config  # noqa: F401  must run before importing application settings
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from qdrant_client import AsyncQdrantClient
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import Session, SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

import app.models as _models  # noqa: F401  ensures all models are registered in SQLModel.metadata
from app.core.config import settings
from app.core.database import async_engine, async_session_maker, sync_engine
from app.core.limiter import limiter
from app.core.rls import MAINTENANCE_CAPABILITY_ROLE, RUNTIME_CAPABILITY_ROLE
from app.core.redis import create_redis_client
from app.core.tenancy import TenantStatus, namespaced_collection, tenant_scope
from app.main import app
from app.models.tenant import Tenant
from app.websocket.manager import ConnectionManager
from tests._db_config import assert_test_database
from tests._llm import (
    DeterministicChatModel,
    has_usable_provider_key,
    real_llm_skip_reason,
)
from tests._redisvl import cleanup_redisvl_resources
from tests._tokenizer import DeterministicTokenEncoder


@pytest.fixture(autouse=True)
def _deterministic_token_encoder(monkeypatch):
    """Keep normal tests independent of external tiktoken assets."""
    monkeypatch.setattr(
        "app.context.token_budget.create_token_encoder",
        DeterministicTokenEncoder,
    )


@pytest.fixture(autouse=True)
def _explicit_local_tenant_context():
    """Bind the documented local bootstrap tenant for legacy test fixtures."""
    with tenant_scope(settings.LOCAL_BOOTSTRAP_TENANT_ID):
        yield


@pytest.fixture(scope="session")
def real_llm():
    """Provide a real LLM instance for tests that require actual model inference.

    Skips unless an operator explicitly opts in and configures a usable provider
    credential. The selected model comes from the trusted real-test route.
    """
    key = settings.OPENAI_API_KEY.get_secret_value()
    dashscope_key = settings.DASHSCOPE_API_KEY.get_secret_value()
    skip_reason = real_llm_skip_reason(
        explicit_opt_in=settings.RUN_REAL_LLM_TESTS,
        openai_key=key,
        dashscope_key=dashscope_key,
    )
    if skip_reason is not None:
        pytest.skip(skip_reason)

    from app.model_gateway.factory import create_model_client

    provider = "openai" if has_usable_provider_key(key) else "dashscope"
    return create_model_client(
        settings.REAL_LLM_TEST_ROUTE,
        provider_override=provider,
        temperature=0.0,
        timeout=30.0,
    )


@pytest_asyncio.fixture(scope="session", autouse=True, loop_scope="session")
async def db_setup():
    assert_test_database(settings.POSTGRES_DB)
    setup_engine = create_async_engine(settings.MIGRATION_DATABASE_URL)
    try:
        async with setup_engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.drop_all)
            await conn.run_sync(SQLModel.metadata.create_all)
            await conn.execute(
                text(
                    "GRANT USAGE ON SCHEMA public TO "
                    f"{RUNTIME_CAPABILITY_ROLE}, {MAINTENANCE_CAPABILITY_ROLE}"
                )
            )
            await conn.execute(
                text(
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "
                    f"{RUNTIME_CAPABILITY_ROLE}, {MAINTENANCE_CAPABILITY_ROLE}"
                )
            )
            await conn.execute(
                text(
                    "GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO "
                    f"{RUNTIME_CAPABILITY_ROLE}, {MAINTENANCE_CAPABILITY_ROLE}"
                )
            )
            tenant_id = settings.LOCAL_BOOTSTRAP_TENANT_ID
            await conn.execute(
                text(
                    "INSERT INTO tenants (id, slug, display_name, status) "
                    "VALUES (:tenant_id, :tenant_id, 'Local Bootstrap Tenant', :status)"
                ),
                {"tenant_id": tenant_id, "status": TenantStatus.ACTIVE},
            )
        yield
    finally:
        await setup_engine.dispose()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def test_maintenance_engine(db_setup: None) -> AsyncIterator[AsyncEngine]:
    """Provide the test-harness-only connection used for global database cleanup.

    This connection deliberately uses the administrative migration URL. It is never passed to
    application, repository, API, or worker code; those paths continue to use the least-privilege
    runtime URL and remain subject to PostgreSQL RLS. The explicit fixture boundary prevents a
    cleanup privilege from becoming an ambient application capability.
    """
    engine = create_async_engine(settings.MIGRATION_DATABASE_URL, pool_pre_ping=True)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def active_tenant(db_setup: None) -> AsyncIterator[str]:
    """Create one committed active tenant for a test and remove it afterward."""
    tenant_id = f"test-tenant-{uuid.uuid4().hex[:12]}"
    async with async_session_maker() as session:
        session.add(
            Tenant(
                id=tenant_id,
                slug=tenant_id,
                display_name="Active Test Tenant",
                status=TenantStatus.ACTIVE,
            )
        )
        await session.commit()

    try:
        yield tenant_id
    finally:
        async with async_session_maker() as session:
            tenant = await session.get(Tenant, tenant_id)
            if tenant is not None:
                await session.delete(tenant)
                await session.commit()


@pytest.fixture
def tenant_context(active_tenant: str) -> Iterator[str]:
    """Bind a committed active test tenant for the duration of one test."""
    with tenant_scope(active_tenant):
        yield active_tenant


@pytest_asyncio.fixture(scope="function", autouse=True, loop_scope="session")
async def _truncate_leaky_tables(test_maintenance_engine: AsyncEngine):
    """Reset shared/leaky tables through the explicit test-maintenance capability only."""
    async with test_maintenance_engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE conversation_runtime_events, conversation_tool_executions, conversation_runs, conversation_turns, conversations, sensitive_export_artifacts, approval_requests, compliance_audit_events, authorization_audit_events, external_identities, task_execution_receipts, outbox_events, message_feedbacks, quality_scores, review_tickets, token_usage_logs, optimization_suggestions, graph_execution_logs, graph_node_logs RESTART IDENTITY CASCADE"
            )
        )
    yield


@pytest_asyncio.fixture(loop_scope="function")
async def client():
    limiter.reset()
    app.state.manager = ConnectionManager()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture(scope="function", loop_scope="session")
async def db_session():
    async with async_engine.connect() as conn:
        await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        await session.begin_nested()
        try:
            yield session
        finally:
            await session.rollback()
            await conn.rollback()
            await session.close()


@pytest.fixture
def db_sync_session():
    with sync_engine.connect() as conn:
        trans = conn.begin()
        session = Session(bind=conn, expire_on_commit=False)
        try:
            yield session
        finally:
            if trans.is_active:
                trans.rollback()
            session.close()


@pytest_asyncio.fixture(scope="function", loop_scope="session")
async def redis_client():
    client = create_redis_client()
    prefix = f"test:{uuid.uuid4().hex}:"
    object.__setattr__(client, "_test_prefix", prefix)
    try:
        yield client
    finally:
        keys = []
        stored_prefix = object.__getattribute__(client, "_test_prefix")
        async for key in client.scan_iter(match=f"{stored_prefix}*"):
            keys.append(key)
        if keys:
            await client.delete(*keys)
        await client.aclose()


@pytest_asyncio.fixture(scope="function", loop_scope="session")
async def redis_checkpointer():
    from langgraph.checkpoint.redis import AsyncRedisSaver

    client = Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=0,
        password=settings.REDIS_PASSWORD.get_secret_value(),
        decode_responses=True,
        socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
        socket_connect_timeout=settings.REDIS_SOCKET_CONNECT_TIMEOUT,
    )
    prefix = f"test_checkpoint_{uuid.uuid4().hex}"
    write_prefix = f"{prefix}_write"
    saver = AsyncRedisSaver(
        redis_client=client,
        checkpoint_prefix=prefix,
        checkpoint_write_prefix=write_prefix,
    )
    try:
        await saver.setup()
        yield saver
    finally:
        await cleanup_redisvl_resources(
            client,
            saver,
            checkpoint_prefix=prefix,
            checkpoint_write_prefix=write_prefix,
        )
        await client.aclose()


@pytest_asyncio.fixture(scope="function", loop_scope="session")
async def qdrant_client():
    qdrant_key = settings.QDRANT_API_KEY.get_secret_value()
    client = AsyncQdrantClient(
        url=settings.QDRANT_URL,
        api_key=qdrant_key if qdrant_key else None,
        timeout=settings.QDRANT_TIMEOUT,
    )
    collection_name = f"test_{uuid.uuid4().hex}"
    try:
        yield client, collection_name
    finally:
        for candidate in (collection_name, namespaced_collection(collection_name)):
            if await client.collection_exists(candidate):
                await client.delete_collection(candidate)
        await client.close()


@pytest.fixture
def deterministic_llm():
    return DeterministicChatModel()


def pytest_runtest_setup(item):
    if any(mark.name == "requires_llm" for mark in item.iter_markers()):
        key = settings.OPENAI_API_KEY.get_secret_value()
        dashscope_key = settings.DASHSCOPE_API_KEY.get_secret_value()
        skip_reason = real_llm_skip_reason(
            explicit_opt_in=settings.RUN_REAL_LLM_TESTS,
            openai_key=key,
            dashscope_key=dashscope_key,
        )
        if skip_reason is not None:
            pytest.skip(skip_reason)
