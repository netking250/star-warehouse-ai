"""Real PostgreSQL verification for database-enforced tenant isolation."""

# ruff: noqa: I001 -- test service isolation must be configured before app imports.

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import tempfile
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession as SQLAlchemyAsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

import tests._db_config  # noqa: F401  configure isolated services before app imports
import app.core.database as database_module
import app.models  # noqa: F401  register the complete production model inventory
from app.authorization.policy import (
    AuthenticatedPrincipal,
    AuthorizationPolicy,
    Role,
    Scope,
    authorize,
    resolve_authorization_context,
)
from app.core.config import settings
from app.core.database_roles import DatabaseLogin, provision_database_logins
from app.core.rls import (
    DATABASE_TENANT_SETTING,
    MAINTENANCE_CAPABILITY_ROLE,
    RUNTIME_CAPABILITY_ROLE,
    bind_database_transaction,
)
from app.core.tenancy import (
    TenantContext,
    TenantStatus,
    clear_current_tenant,
    reset_current_tenant,
    tenant_scope,
)
from app.memory.structured_manager import StructuredMemoryManager
from app.models.user import User
from app.task_runtime.binding import task_execution_scope
from app.task_runtime.context import build_task_context
from migrations.versions.a5b6c7d8e9f0_enable_postgresql_rls import (
    POLICY_NAME,
    TENANT_OWNED_TABLES,
)
from migrations.versions.b6c7d8e9f0a1_add_external_identity_bindings import (
    T08_TENANT_OWNED_TABLES,
)
from migrations.versions.c7d8e9f0a1b2_add_authorization_audit_events import (
    T09_TENANT_OWNED_TABLES,
)
from migrations.versions.d8e9f0a1b2c3_add_compliance_lifecycle import (
    T11_TENANT_OWNED_TABLES,
)
from migrations.versions.e9f0a1b2c3d4_add_durable_conversation_runtime import (
    T12_TENANT_OWNED_TABLES,
)

PROTECTED_TENANT_TABLES = (
    TENANT_OWNED_TABLES
    + T08_TENANT_OWNED_TABLES
    + T09_TENANT_OWNED_TABLES
    + T11_TENANT_OWNED_TABLES
    + T12_TENANT_OWNED_TABLES
)


@dataclass(slots=True)
class RLSDatabase:
    """Temporary migrated database and least-privilege connection factories."""

    database_name: str
    runtime_login: str
    maintenance_login: str
    runtime_engine: AsyncEngine
    runtime_sessions: async_sessionmaker[SQLAlchemyAsyncSession]
    structured_runtime_sessions: async_sessionmaker[SQLModelAsyncSession]
    maintenance_engine: AsyncEngine
    sync_runtime_url: str
    tenant_a: str
    tenant_b: str
    order_a_id: int
    order_b_id: int
    user_a_id: int
    user_b_id: int


def _url(
    base: URL,
    *,
    drivername: str,
    database: str,
    username: str | None = None,
    password: str | None = None,
) -> str:
    return base.set(
        drivername=drivername,
        database=database,
        username=username if username is not None else base.username,
        password=password if password is not None else base.password,
    ).render_as_string(hide_password=False)


async def _run_alembic_upgrade(database_name: str) -> None:
    log_path = Path(tempfile.gettempdir()) / f"t07-alembic-{database_name}.log"
    environment = os.environ.copy()
    environment["POSTGRES_DB"] = database_name
    environment["POSTGRES_USER"] = settings.POSTGRES_USER
    environment["POSTGRES_PASSWORD"] = settings.POSTGRES_PASSWORD.get_secret_value()
    repository_root = Path(__file__).resolve().parents[2]

    def run() -> subprocess.CompletedProcess[str]:
        with log_path.open("w", encoding="utf-8") as log_file:
            return subprocess.run(
                [sys.executable, "-m", "alembic", "upgrade", "head"],
                cwd=repository_root,
                env=environment,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )

    result = await asyncio.to_thread(run)
    if result.returncode != 0:
        tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-20:]
        pytest.fail("Alembic upgrade failed:\n" + "\n".join(tail))


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def rls_database() -> AsyncIterator[RLSDatabase]:
    """Create a fresh migrated database and disposable runtime login roles."""
    suffix = uuid.uuid4().hex[:10]
    database_name = f"test_t07_rls_{suffix}"
    runtime_login = f"t07_runtime_{suffix}"
    maintenance_login = f"t07_maintenance_{suffix}"
    login_password = f"t07-{uuid.uuid4().hex}"
    tenant_a = f"t07-a-{suffix}"
    tenant_b = f"t07-b-{suffix}"
    admin_base = make_url(settings.MIGRATION_DATABASE_URL)
    admin_server_url = _url(
        admin_base,
        drivername="postgresql+asyncpg",
        database="postgres",
    )
    admin_database_url = _url(
        admin_base,
        drivername="postgresql+asyncpg",
        database=database_name,
    )
    server_engine = create_async_engine(admin_server_url, isolation_level="AUTOCOMMIT")
    runtime_engine: AsyncEngine | None = None
    maintenance_engine: AsyncEngine | None = None

    try:
        async with server_engine.connect() as connection:
            await connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
        await _run_alembic_upgrade(database_name)
        await provision_database_logins(
            admin_database_url=admin_database_url,
            runtime_login=DatabaseLogin(
                username=runtime_login,
                password=login_password,
                capability_role=RUNTIME_CAPABILITY_ROLE,
            ),
            maintenance_login=DatabaseLogin(
                username=maintenance_login,
                password=login_password,
                capability_role=MAINTENANCE_CAPABILITY_ROLE,
            ),
        )

        runtime_url = _url(
            admin_base,
            drivername="postgresql+asyncpg",
            database=database_name,
            username=runtime_login,
            password=login_password,
        )
        sync_runtime_url = _url(
            admin_base,
            drivername="postgresql+psycopg2",
            database=database_name,
            username=runtime_login,
            password=login_password,
        )
        maintenance_url = _url(
            admin_base,
            drivername="postgresql+asyncpg",
            database=database_name,
            username=maintenance_login,
            password=login_password,
        )
        runtime_engine = create_async_engine(
            runtime_url,
            pool_size=1,
            max_overflow=0,
            pool_pre_ping=True,
        )
        runtime_sessions = async_sessionmaker(
            runtime_engine,
            class_=SQLAlchemyAsyncSession,
            expire_on_commit=False,
        )
        structured_runtime_sessions = async_sessionmaker(
            runtime_engine,
            class_=SQLModelAsyncSession,
            expire_on_commit=False,
        )
        maintenance_engine = create_async_engine(
            maintenance_url,
            pool_size=1,
            max_overflow=0,
            pool_pre_ping=True,
        )

        admin_database_engine = create_async_engine(admin_database_url)
        try:
            async with admin_database_engine.begin() as connection:
                await connection.execute(
                    text(
                        "INSERT INTO tenants (id, slug, display_name, status) VALUES "
                        "(:tenant_a, :tenant_a, 'T07 Tenant A', 'ACTIVE'), "
                        "(:tenant_b, :tenant_b, 'T07 Tenant B', 'ACTIVE')"
                    ),
                    {"tenant_a": tenant_a, "tenant_b": tenant_b},
                )
                user_a_id = await connection.scalar(
                    text(
                        "INSERT INTO users "
                        "(tenant_id, username, password_hash, email, full_name, is_admin, "
                        "role, is_active) VALUES "
                        "(:tenant_id, 't07-a', 'hash', 'a@t07.invalid', 'Tenant A', false, "
                        "'customer', true) RETURNING id"
                    ),
                    {"tenant_id": tenant_a},
                )
                user_b_id = await connection.scalar(
                    text(
                        "INSERT INTO users "
                        "(tenant_id, username, password_hash, email, full_name, is_admin, "
                        "role, is_active) VALUES "
                        "(:tenant_id, 't07-b', 'hash', 'b@t07.invalid', 'Tenant B', false, "
                        "'customer', true) RETURNING id"
                    ),
                    {"tenant_id": tenant_b},
                )
                if not isinstance(user_a_id, int) or not isinstance(user_b_id, int):
                    raise RuntimeError("T07 user seed did not return integer identifiers")
                order_a_id = await connection.scalar(
                    text(
                        "INSERT INTO orders "
                        "(tenant_id, order_sn, user_id, status, total_amount, items, "
                        "shipping_address) VALUES "
                        "(:tenant_id, 'T07-A', :user_id, 'PENDING', 10.00, '[]'::json, "
                        "'Tenant A address') RETURNING id"
                    ),
                    {"tenant_id": tenant_a, "user_id": user_a_id},
                )
                order_b_id = await connection.scalar(
                    text(
                        "INSERT INTO orders "
                        "(tenant_id, order_sn, user_id, status, total_amount, items, "
                        "shipping_address) VALUES "
                        "(:tenant_id, 'T07-B', :user_id, 'PENDING', 20.00, '[]'::json, "
                        "'Tenant B address') RETURNING id"
                    ),
                    {"tenant_id": tenant_b, "user_id": user_b_id},
                )
                if not isinstance(order_a_id, int) or not isinstance(order_b_id, int):
                    raise RuntimeError("T07 order seed did not return integer identifiers")
                await connection.execute(
                    text(
                        "INSERT INTO user_facts "
                        "(tenant_id, user_id, fact_type, content, confidence) VALUES "
                        "(:tenant_a, :user_a_id, 'preference', 'tenant-a-fact', 0.9), "
                        "(:tenant_b, :user_b_id, 'preference', 'tenant-b-fact', 0.9)"
                    ),
                    {
                        "tenant_a": tenant_a,
                        "tenant_b": tenant_b,
                        "user_a_id": user_a_id,
                        "user_b_id": user_b_id,
                    },
                )
        finally:
            await admin_database_engine.dispose()

        yield RLSDatabase(
            database_name=database_name,
            runtime_login=runtime_login,
            maintenance_login=maintenance_login,
            runtime_engine=runtime_engine,
            runtime_sessions=runtime_sessions,
            structured_runtime_sessions=structured_runtime_sessions,
            maintenance_engine=maintenance_engine,
            sync_runtime_url=sync_runtime_url,
            tenant_a=tenant_a,
            tenant_b=tenant_b,
            order_a_id=order_a_id,
            order_b_id=order_b_id,
            user_a_id=user_a_id,
            user_b_id=user_b_id,
        )
    finally:
        if runtime_engine is not None:
            await runtime_engine.dispose()
        if maintenance_engine is not None:
            await maintenance_engine.dispose()
        async with server_engine.connect() as connection:
            await connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :database_name AND pid <> pg_backend_pid()"
                ),
                {"database_name": database_name},
            )
            await connection.exec_driver_sql(f'DROP DATABASE IF EXISTS "{database_name}"')
            for role in (runtime_login, maintenance_login):
                await connection.exec_driver_sql(f'DROP ROLE IF EXISTS "{role}"')
        await server_engine.dispose()


@pytest.mark.asyncio(loop_scope="session")
async def test_raw_query_returns_only_bound_tenant_rows(rls_database: RLSDatabase) -> None:
    """A raw query without an application predicate must still be tenant-scoped."""
    with tenant_scope(rls_database.tenant_a):
        async with rls_database.runtime_sessions() as session:
            rows = (
                await session.execute(text("SELECT tenant_id, order_sn FROM orders ORDER BY id"))
            ).all()

    assert rows == [(rls_database.tenant_a, "T07-A")]


@pytest.mark.asyncio(loop_scope="session")
async def test_authorized_application_super_admin_still_cannot_bypass_rls(
    rls_database: RLSDatabase,
) -> None:
    """An allowed application role must remain constrained by the runtime RLS boundary."""
    with tenant_scope(rls_database.tenant_a):
        async with rls_database.structured_runtime_sessions() as session, session.begin():
            user = User(
                tenant_id=rls_database.tenant_a,
                username="t09-application-admin",
                password_hash="unused-test-hash",
                email="t09-application-admin@example.com",
                full_name="T09 Application Admin",
                role=Role.SUPER_ADMIN.value,
                is_admin=True,
                is_active=True,
            )
            session.add(user)
            await session.flush()
            if user.id is None:
                raise RuntimeError("T09 RLS smoke user ID was not assigned")

            context = await resolve_authorization_context(
                session,
                AuthenticatedPrincipal(
                    tenant_id=rls_database.tenant_a,
                    user_id=user.id,
                    session_id="t09-rls-session",
                    correlation_id="t09-rls-correlation",
                    token_id="t09-rls-token",
                ),
                TenantContext(
                    tenant_id=rls_database.tenant_a,
                    slug=rls_database.tenant_a,
                    display_name="T07 Tenant A",
                    status=TenantStatus.ACTIVE,
                ),
            )
            decision = authorize(
                context,
                AuthorizationPolicy(scopes=frozenset({Scope.OPERATIONS_MANAGE})),
            )
            cross_tenant_order = await session.scalar(
                text("SELECT id FROM orders WHERE id = :order_id"),
                {"order_id": rls_database.order_b_id},
            )

    assert decision.allowed
    assert cross_tenant_order is None


async def _read_structured_facts(
    rls_database: RLSDatabase,
    *,
    tenant_id: str,
    user_id: int,
) -> tuple[str, list[tuple[str, str]]]:
    """Read structured facts in an independently owned runtime transaction."""
    manager = StructuredMemoryManager()
    with tenant_scope(tenant_id):
        async with rls_database.structured_runtime_sessions() as session, session.begin():
            effective_role = str(await session.scalar(text("SELECT current_user")))
            facts = await manager.get_user_facts(session, user_id, limit=10)
    return effective_role, [(fact.tenant_id, fact.content) for fact in facts]


@pytest.mark.asyncio(loop_scope="session")
async def test_concurrent_same_tenant_structured_reads_are_isolated(
    rls_database: RLSDatabase,
) -> None:
    """Concurrent Tenant A reads must complete through independent runtime sessions."""
    results = await asyncio.gather(
        *(
            _read_structured_facts(
                rls_database,
                tenant_id=rls_database.tenant_a,
                user_id=rls_database.user_a_id,
            )
            for _ in range(8)
        )
    )

    assert results == [(RUNTIME_CAPABILITY_ROLE, [(rls_database.tenant_a, "tenant-a-fact")])] * 8


@pytest.mark.asyncio(loop_scope="session")
async def test_concurrent_cross_tenant_structured_reads_do_not_contaminate_context(
    rls_database: RLSDatabase,
) -> None:
    """Concurrent Tenant A and B transactions must see only their own facts."""
    tenant_a_result, tenant_b_result = await asyncio.gather(
        _read_structured_facts(
            rls_database,
            tenant_id=rls_database.tenant_a,
            user_id=rls_database.user_a_id,
        ),
        _read_structured_facts(
            rls_database,
            tenant_id=rls_database.tenant_b,
            user_id=rls_database.user_b_id,
        ),
    )

    assert tenant_a_result == (
        RUNTIME_CAPABILITY_ROLE,
        [(rls_database.tenant_a, "tenant-a-fact")],
    )
    assert tenant_b_result == (
        RUNTIME_CAPABILITY_ROLE,
        [(rls_database.tenant_b, "tenant-b-fact")],
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_direct_id_read_update_and_delete_are_blocked(rls_database: RLSDatabase) -> None:
    """Knowing another tenant's primary key must not permit access or mutation."""
    with tenant_scope(rls_database.tenant_a):
        async with rls_database.runtime_sessions() as session, session.begin():
            visible = await session.scalar(
                text("SELECT id FROM orders WHERE id = :order_id"),
                {"order_id": rls_database.order_b_id},
            )
            await session.execute(
                text("UPDATE orders SET status = 'CANCELLED' WHERE id = :order_id"),
                {"order_id": rls_database.order_b_id},
            )
            await session.execute(
                text("DELETE FROM orders WHERE id = :order_id"),
                {"order_id": rls_database.order_b_id},
            )

    assert visible is None
    with tenant_scope(rls_database.tenant_b):
        async with rls_database.runtime_sessions() as session:
            status = await session.scalar(
                text("SELECT status FROM orders WHERE id = :order_id"),
                {"order_id": rls_database.order_b_id},
            )
    assert status == "PENDING"


@pytest.mark.asyncio(loop_scope="session")
async def test_cross_tenant_insert_is_rejected_by_with_check(
    rls_database: RLSDatabase,
) -> None:
    """WITH CHECK must reject a row carrying another tenant's identifier."""
    with tenant_scope(rls_database.tenant_a):
        async with rls_database.runtime_sessions() as session:
            with pytest.raises(DBAPIError, match="row-level security"):
                await session.execute(
                    text(
                        "INSERT INTO orders "
                        "(tenant_id, order_sn, user_id, status, total_amount, items, "
                        "shipping_address) VALUES "
                        "(:tenant_id, 'T07-CROSS', :user_id, 'PENDING', 1.00, '[]'::json, "
                        "'blocked')"
                    ),
                    {"tenant_id": rls_database.tenant_b, "user_id": rls_database.user_b_id},
                )


@pytest.mark.asyncio(loop_scope="session")
async def test_missing_tenant_context_fails_closed_at_database(
    rls_database: RLSDatabase,
) -> None:
    """No ContextVar tenant must expose zero rows and reject writes."""
    token = clear_current_tenant()
    try:
        async with rls_database.runtime_sessions() as session:
            rows = (await session.execute(text("SELECT id FROM orders"))).all()
        assert rows == []

        async with rls_database.runtime_sessions() as session:
            with pytest.raises(DBAPIError, match="row-level security"):
                await session.execute(
                    text(
                        "INSERT INTO orders "
                        "(tenant_id, order_sn, user_id, status, total_amount, items, "
                        "shipping_address) VALUES "
                        "(:tenant_id, 'T07-NONE', :user_id, 'PENDING', 1.00, '[]'::json, "
                        "'blocked')"
                    ),
                    {"tenant_id": rls_database.tenant_b, "user_id": rls_database.user_b_id},
                )
    finally:
        reset_current_tenant(token)


@pytest.mark.asyncio(loop_scope="session")
async def test_pool_reuse_does_not_leak_tenant_or_context(
    rls_database: RLSDatabase,
) -> None:
    """One physical connection must safely serve A, B, then no tenant."""
    backend_pids: list[int] = []
    observed: list[list[str]] = []
    for tenant_id in (rls_database.tenant_a, rls_database.tenant_b):
        with tenant_scope(tenant_id):
            async with rls_database.runtime_sessions() as session:
                backend_pids.append(int(await session.scalar(text("SELECT pg_backend_pid()"))))
                observed.append(
                    list(
                        (
                            await session.execute(
                                text("SELECT tenant_id FROM orders ORDER BY tenant_id")
                            )
                        ).scalars()
                    )
                )

    token = clear_current_tenant()
    try:
        async with rls_database.runtime_sessions() as session:
            backend_pids.append(int(await session.scalar(text("SELECT pg_backend_pid()"))))
            observed.append(
                list((await session.execute(text("SELECT tenant_id FROM orders"))).scalars())
            )
            setting = await session.scalar(
                text("SELECT NULLIF(current_setting(:setting_name, true), '')"),
                {"setting_name": DATABASE_TENANT_SETTING},
            )
    finally:
        reset_current_tenant(token)

    assert len(set(backend_pids)) == 1
    assert observed == [[rls_database.tenant_a], [rls_database.tenant_b], []]
    assert setting is None


def test_worker_task_context_binds_postgresql_tenant(
    rls_database: RLSDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A validated TaskContext must reach a worker database transaction."""
    sync_engine = create_engine(
        rls_database.sync_runtime_url,
        pool_size=1,
        max_overflow=0,
        pool_pre_ping=True,
    )
    runtime_sessions = sessionmaker(sync_engine, class_=Session, expire_on_commit=False)
    monkeypatch.setattr(database_module, "sync_session_maker", runtime_sessions)
    task_context = build_task_context(
        task_name="tests.t07.worker",
        tenant_id=rls_database.tenant_a,
        user_id=1,
        correlation_id=f"t07-{uuid.uuid4().hex}",
        trace_id=None,
        thread_id="t07-worker",
    )
    try:
        with (
            task_execution_scope(
                task_context,
                task_name="celery.tests.t07.worker",
                task_id="t07-worker",
            ),
            runtime_sessions() as session,
        ):
            tenants = list(
                session.execute(text("SELECT tenant_id FROM orders ORDER BY tenant_id")).scalars()
            )
        assert tenants == [rls_database.tenant_a]
    finally:
        sync_engine.dispose()


@pytest.mark.asyncio(loop_scope="session")
async def test_runtime_login_and_effective_role_cannot_bypass_rls(
    rls_database: RLSDatabase,
) -> None:
    """The configured runtime login must be non-privileged and use the RLS role."""
    with tenant_scope(rls_database.tenant_a):
        async with rls_database.runtime_sessions() as session:
            identity = (
                await session.execute(
                    text(
                        "SELECT session_user, current_user, role.rolsuper, role.rolbypassrls "
                        "FROM pg_roles AS role WHERE role.rolname = session_user"
                    )
                )
            ).one()
            owner = await session.scalar(
                text(
                    "SELECT owner.rolname FROM pg_class AS relation "
                    "JOIN pg_roles AS owner ON owner.oid = relation.relowner "
                    "WHERE relation.oid = 'orders'::regclass"
                )
            )

    assert identity == (rls_database.runtime_login, RUNTIME_CAPABILITY_ROLE, False, False)
    assert owner not in {rls_database.runtime_login, RUNTIME_CAPABILITY_ROLE}

    with tenant_scope(rls_database.tenant_a):
        async with rls_database.runtime_sessions() as session:
            with pytest.raises(DBAPIError, match="permission denied to set role"):
                await session.execute(text(f"SET LOCAL ROLE {MAINTENANCE_CAPABILITY_ROLE}"))


@pytest.mark.asyncio(loop_scope="session")
async def test_maintenance_role_is_global_only_without_tenant_context(
    rls_database: RLSDatabase,
) -> None:
    """The separate maintenance login may scan globally but narrows when tenant-bound."""
    async with rls_database.maintenance_engine.connect() as connection:
        async with connection.begin():
            await connection.run_sync(
                lambda sync_connection: bind_database_transaction(
                    sync_connection,
                    capability="maintenance",
                    tenant_id=None,
                )
            )
            global_tenants = list(
                (
                    await connection.execute(
                        text("SELECT tenant_id FROM orders ORDER BY tenant_id")
                    )
                ).scalars()
            )
        async with connection.begin():
            await connection.run_sync(
                lambda sync_connection: bind_database_transaction(
                    sync_connection,
                    capability="maintenance",
                    tenant_id=rls_database.tenant_a,
                )
            )
            tenant_rows = list(
                (
                    await connection.execute(
                        text("SELECT tenant_id FROM orders ORDER BY tenant_id")
                    )
                ).scalars()
            )

    assert global_tenants == [rls_database.tenant_a, rls_database.tenant_b]
    assert tenant_rows == [rls_database.tenant_a]


@pytest.mark.asyncio(loop_scope="session")
async def test_tenant_inventory_has_forced_all_command_policies(
    rls_database: RLSDatabase,
) -> None:
    """Every current tenant-owned table must have structural RLS protection."""
    model_tables = {
        table.name for table in SQLModel.metadata.tables.values() if "tenant_id" in table.c
    }
    assert model_tables == set(PROTECTED_TENANT_TABLES)

    with tenant_scope(rls_database.tenant_a):
        async with rls_database.runtime_sessions() as session:
            relations = (
                await session.execute(
                    text(
                        "SELECT relation.relname, relation.relrowsecurity, "
                        "relation.relforcerowsecurity "
                        "FROM pg_class AS relation "
                        "JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace "
                        "WHERE namespace.nspname = 'public' AND relation.relname = ANY(:tables)"
                    ),
                    {"tables": list(PROTECTED_TENANT_TABLES)},
                )
            ).all()
            policies = (
                await session.execute(
                    text(
                        "SELECT tablename, policyname, cmd, qual IS NOT NULL, "
                        "with_check IS NOT NULL FROM pg_policies "
                        "WHERE schemaname = 'public' AND tablename = ANY(:tables)"
                    ),
                    {"tables": list(PROTECTED_TENANT_TABLES)},
                )
            ).all()
            capability_roles = (
                await session.execute(
                    text(
                        "SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, "
                        "rolinherit, rolbypassrls FROM pg_roles "
                        "WHERE rolname = ANY(:roles)"
                    ),
                    {"roles": [RUNTIME_CAPABILITY_ROLE, MAINTENANCE_CAPABILITY_ROLE]},
                )
            ).all()
            capability_memberships = (
                await session.execute(
                    text(
                        "SELECT member.rolname FROM pg_auth_members AS membership "
                        "JOIN pg_roles AS member ON member.oid = membership.member "
                        "WHERE member.rolname = ANY(:roles)"
                    ),
                    {"roles": [RUNTIME_CAPABILITY_ROLE, MAINTENANCE_CAPABILITY_ROLE]},
                )
            ).all()

    assert {name for name, enabled, forced in relations if enabled and forced} == set(
        PROTECTED_TENANT_TABLES
    )
    protected = {
        table
        for table, policy, command, has_using, has_check in policies
        if policy == POLICY_NAME and command == "ALL" and has_using and has_check
    }
    assert protected == set(PROTECTED_TENANT_TABLES)
    assert {
        name
        for name, can_login, is_super, can_create_db, can_create_role, inherits, bypasses_rls in (
            capability_roles
        )
        if not any((can_login, is_super, can_create_db, can_create_role, inherits, bypasses_rls))
    } == {RUNTIME_CAPABILITY_ROLE, MAINTENANCE_CAPABILITY_ROLE}
    assert capability_memberships == []


@pytest.mark.asyncio(loop_scope="session")
async def test_conversation_runtime_table_is_database_tenant_isolated(
    rls_database: RLSDatabase,
) -> None:
    conversation_id = f"t12-conversation-{uuid.uuid4().hex}"
    with tenant_scope(rls_database.tenant_a):
        async with rls_database.runtime_sessions() as session, session.begin():
            await session.execute(
                text(
                    "INSERT INTO conversations "
                    "(tenant_id, conversation_id, user_id, revision) "
                    "VALUES (:tenant_id, :conversation_id, :user_id, 0)"
                ),
                {
                    "tenant_id": rls_database.tenant_a,
                    "conversation_id": conversation_id,
                    "user_id": rls_database.user_a_id,
                },
            )

    with tenant_scope(rls_database.tenant_b):
        async with rls_database.runtime_sessions() as session, session.begin():
            hidden = await session.scalar(
                text("SELECT conversation_id FROM conversations WHERE conversation_id = :id"),
                {"id": conversation_id},
            )
            with pytest.raises(DBAPIError):
                await session.execute(
                    text(
                        "INSERT INTO conversations "
                        "(tenant_id, conversation_id, user_id, revision) "
                        "VALUES (:tenant_id, :conversation_id, :user_id, 0)"
                    ),
                    {
                        "tenant_id": rls_database.tenant_a,
                        "conversation_id": f"cross-{conversation_id}",
                        "user_id": rls_database.user_a_id,
                    },
                )

    assert hidden is None


@pytest.mark.asyncio(loop_scope="session")
async def test_runtime_can_append_but_cannot_mutate_immutable_audit(
    rls_database: RLSDatabase,
) -> None:
    """Prove immutability at raw PostgreSQL runtime-role boundary."""
    async with rls_database.runtime_engine.connect() as connection:
        async with connection.begin():
            await connection.run_sync(
                lambda sync_connection: bind_database_transaction(
                    sync_connection,
                    capability="runtime",
                    tenant_id=rls_database.tenant_a,
                )
            )
            audit_id = (
                await connection.execute(
                    text(
                        "INSERT INTO compliance_audit_events "
                        "(tenant_id, event_type, actor_user_id, actor_type, target_type, "
                        "target_reference, outcome, reason_code, correlation_id, event_metadata) "
                        "VALUES (:tenant_id, 'sensitive_export.requested', :actor_id, 'USER', "
                        "'feedback_export', 'approval-test', 'PENDING', 'APPROVAL_REQUIRED', "
                        "'t11-immutable-audit', CAST(:metadata AS JSON)) RETURNING id"
                    ),
                    {
                        "tenant_id": rls_database.tenant_a,
                        "actor_id": rls_database.user_a_id,
                        "metadata": '{"operation_hash":"safe-hash","record_count":0}',
                    },
                )
            ).scalar_one()
            authorization_audit_id = (
                await connection.execute(
                    text(
                        "INSERT INTO authorization_audit_events "
                        "(tenant_id, actor_user_id, target_user_id, action, decision, "
                        "reason_code, correlation_id) VALUES (:tenant_id, :actor_id, :actor_id, "
                        "'membership.enabled', 'ALLOW', 'ALLOW', 't11-auth-immutable') RETURNING id"
                    ),
                    {
                        "tenant_id": rls_database.tenant_a,
                        "actor_id": rls_database.user_a_id,
                    },
                )
            ).scalar_one()

        for statement, target_id in (
            (
                "UPDATE compliance_audit_events SET outcome = 'CHANGED' WHERE id = :audit_id",
                audit_id,
            ),
            ("DELETE FROM compliance_audit_events WHERE id = :audit_id", audit_id),
            (
                "UPDATE authorization_audit_events SET decision = 'DENY' WHERE id = :audit_id",
                authorization_audit_id,
            ),
            (
                "DELETE FROM authorization_audit_events WHERE id = :audit_id",
                authorization_audit_id,
            ),
        ):
            with pytest.raises(DBAPIError):
                async with connection.begin():
                    await connection.run_sync(
                        lambda sync_connection: bind_database_transaction(
                            sync_connection,
                            capability="runtime",
                            tenant_id=rls_database.tenant_a,
                        )
                    )
                    await connection.execute(text("SET LOCAL app.application_role = 'super_admin'"))
                    await connection.execute(text(statement), {"audit_id": target_id})

        async with connection.begin():
            await connection.run_sync(
                lambda sync_connection: bind_database_transaction(
                    sync_connection,
                    capability="runtime",
                    tenant_id=rls_database.tenant_a,
                )
            )
            event = (
                await connection.execute(
                    text(
                        "SELECT tenant_id, actor_user_id, event_type, correlation_id, outcome, "
                        "reason_code, event_metadata FROM compliance_audit_events WHERE id = :id"
                    ),
                    {"id": audit_id},
                )
            ).one()

    assert event.tenant_id == rls_database.tenant_a
    assert event.actor_user_id == rls_database.user_a_id
    assert event.event_type == "sensitive_export.requested"
    assert event.correlation_id == "t11-immutable-audit"
    assert event.outcome == "PENDING"
    assert event.reason_code == "APPROVAL_REQUIRED"
    assert not {"password", "token", "cookie", "csrf"}.intersection(event.event_metadata)
