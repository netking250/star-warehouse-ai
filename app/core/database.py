# app/core/database.py
from collections.abc import AsyncGenerator, Generator

from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session as SQLAlchemySession
from sqlalchemy.orm import sessionmaker, with_loader_criteria
from sqlmodel import Session
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.tenancy import TenantIsolationError, get_current_tenant_id
from app.models.tenant import TenantScopedModel


@event.listens_for(SQLAlchemySession, "do_orm_execute")
def _enforce_tenant_select(execute_state) -> None:
    """Inject the active tenant predicate into every ORM SELECT."""
    if not execute_state.is_select or execute_state.execution_options.get("skip_tenant_scope"):
        return
    tenant_id = get_current_tenant_id()
    statement = execute_state.statement
    for mapper in execute_state.all_mappers:
        model = mapper.class_
        if not issubclass(model, TenantScopedModel):
            continue
        statement = statement.options(
            with_loader_criteria(
                model,
                lambda scoped_model: scoped_model.tenant_id == tenant_id,
                include_aliases=True,
            )
        )
    execute_state.statement = statement


@event.listens_for(SQLAlchemySession, "before_flush")
def _enforce_tenant_writes(session: SQLAlchemySession, _flush_context, _instances) -> None:
    """Reject inserts and updates that target another tenant."""
    active_tenant = get_current_tenant_id()
    for record in session.new.union(session.dirty):
        if isinstance(record, TenantScopedModel) and record.tenant_id != active_tenant:
            raise TenantIsolationError(
                f"Cannot write tenant {record.tenant_id!r} while scoped to {active_tenant!r}"
            )


_async_connect_args = {
    "timeout": settings.DB_CONNECT_TIMEOUT,
    "server_settings": {"application_name": "ecommerce-agent", "jit": "off"},
}

_sync_connect_args = {
    "connect_timeout": settings.DB_CONNECT_TIMEOUT,
    "options": "-c application_name=ecommerce-agent -c jit=off",
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
