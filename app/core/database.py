# app/core/database.py
import logging
from collections.abc import AsyncGenerator, Generator

from sqlalchemy import create_engine, event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session as SQLAlchemySession
from sqlalchemy.orm import SessionTransaction, sessionmaker, with_loader_criteria
from sqlmodel import Session
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.rls import bind_database_transaction
from app.core.tenancy import TenantIsolationError, get_current_tenant_id, get_optional_tenant_id
from app.models.tenant import TenantScopedModel

logger = logging.getLogger(__name__)


@event.listens_for(SQLAlchemySession, "do_orm_execute")
def _enforce_tenant_select(execute_state) -> None:
    """Inject the active tenant predicate into ORM reads and bulk mutations."""
    _refresh_database_tenant_context(execute_state.session)
    if not (
        execute_state.is_select or execute_state.is_update or execute_state.is_delete
    ) or execute_state.execution_options.get("skip_tenant_scope"):
        return
    statement = execute_state.statement
    scoped_models: list[type[TenantScopedModel]] = []
    for mapper in execute_state.all_mappers:
        model = mapper.class_
        if not issubclass(model, TenantScopedModel):
            continue
        scoped_models.append(model)

    if not scoped_models:
        return

    tenant_id = get_current_tenant_id()
    for model in scoped_models:
        if execute_state.is_select:
            statement = statement.options(
                with_loader_criteria(
                    model,
                    lambda scoped_model: scoped_model.tenant_id == tenant_id,
                    include_aliases=True,
                )
            )
        else:
            statement = statement.where(model.tenant_id == tenant_id)
    execute_state.statement = statement


@event.listens_for(SQLAlchemySession, "before_flush")
def _enforce_tenant_writes(session: SQLAlchemySession, _flush_context, _instances) -> None:
    """Reject instance writes and relationships that cross tenant ownership."""
    _refresh_database_tenant_context(session)
    scoped_records = [
        record
        for record in session.new.union(session.dirty).union(session.deleted)
        if isinstance(record, TenantScopedModel)
    ]
    if not scoped_records:
        return
    active_tenant = get_current_tenant_id()
    for record in scoped_records:
        if record.tenant_id != active_tenant:
            logger.warning(
                "Cross-tenant write rejected",
                extra={
                    "event": TenantIsolationError.code,
                    "tenant_id": active_tenant,
                    "resource_type": type(record).__name__,
                    "operation": "write",
                },
            )
            raise TenantIsolationError(
                f"Cannot write tenant {record.tenant_id!r} while scoped to {active_tenant!r}"
            )
        mapper = record.__mapper__
        for column in mapper.columns:
            foreign_value = getattr(record, column.key)
            if foreign_value is None:
                continue
            for foreign_key in column.foreign_keys:
                target_column = foreign_key.column
                tenant_column = target_column.table.c.get("tenant_id")
                if tenant_column is None:
                    continue
                related_tenant = session.execute(
                    select(tenant_column)
                    .where(target_column == foreign_value)
                    .execution_options(skip_tenant_scope=True)
                ).scalar_one_or_none()
                if related_tenant is None or related_tenant == active_tenant:
                    continue
                logger.warning(
                    "Cross-tenant relationship rejected",
                    extra={
                        "event": TenantIsolationError.code,
                        "tenant_id": active_tenant,
                        "resource_type": type(record).__name__,
                        "operation": "relationship_write",
                    },
                )
                raise TenantIsolationError(
                    f"Cannot create relationship from tenant {active_tenant!r} "
                    f"to tenant {related_tenant!r}"
                )


@event.listens_for(SQLAlchemySession, "after_begin")
def _bind_database_tenant_context(session: SQLAlchemySession, _transaction, connection) -> None:
    """Bind the effective database role and tenant at transaction start."""
    tenant_id = get_optional_tenant_id()
    bind_database_transaction(
        connection,
        capability=settings.DB_CAPABILITY,
        tenant_id=tenant_id,
    )
    session.info["database_tenant_id"] = tenant_id


@event.listens_for(SQLAlchemySession, "after_transaction_end")
def _clear_database_tenant_context(
    session: SQLAlchemySession, transaction: SessionTransaction
) -> None:
    """Clear transaction-local binding metadata after the outer transaction ends."""
    if transaction.parent is None:
        session.info.pop("database_tenant_id", None)


def _refresh_database_tenant_context(session: SQLAlchemySession) -> None:
    """Refresh a tenant resolved after the current transaction already began."""
    tenant_id = get_optional_tenant_id()
    if not session.in_transaction() or "database_tenant_id" not in session.info:
        return
    if session.info.get("database_tenant_id") == tenant_id:
        return
    connection = session.connection()
    if session.info.get("database_tenant_id") == tenant_id:
        return
    bind_database_transaction(
        connection,
        capability=settings.DB_CAPABILITY,
        tenant_id=tenant_id,
    )
    session.info["database_tenant_id"] = tenant_id


_async_connect_args = {
    "timeout": settings.DB_CONNECT_TIMEOUT,
    "server_settings": {"application_name": settings.SERVICE_NAME, "jit": "off"},
}

_sync_connect_args = {
    "connect_timeout": settings.DB_CONNECT_TIMEOUT,
    "options": f"-c application_name={settings.SERVICE_NAME} -c jit=off",
}

# 异步引擎与 Session 工厂（FastAPI / Agent 使用）
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    connect_args=_async_connect_args,
)
async_session_maker = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

# 同步引擎与 Session 工厂（Celery 任务使用）
sync_engine = create_engine(
    settings.SYNC_DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    connect_args=_sync_connect_args,
)
sync_session_maker = sessionmaker(sync_engine, class_=Session, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


def get_sync_session() -> Generator[Session, None, None]:
    with sync_session_maker() as session:
        yield session


# engine and session factory are ready for use
