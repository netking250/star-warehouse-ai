"""PostgreSQL integration coverage for the canonical local bootstrap dataset."""

import pytest
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.bootstrap.local_data import (
    LocalBootstrapConfig,
    _ensure_tenant,
    bootstrap_business_records,
)
from app.core.config import settings
from app.models.audit import AuditLog
from app.models.complaint import ComplaintTicket
from app.models.memory import AgentConfig, RoutingRule
from app.models.order import Order
from app.models.outbox import OutboxEvent
from app.models.refund import RefundApplication
from app.models.tenant import Tenant
from app.models.user import User


def _config() -> LocalBootstrapConfig:
    return LocalBootstrapConfig(
        enabled=True,
        environment="development",
        tenant_id=settings.LOCAL_BOOTSTRAP_TENANT_ID,
        tenant_name="Northstar Outfitters Local UAT",
        customer_username="northstar_customer",
        customer_password=SecretStr("local-customer-change-me"),
        customer_email="customer@northstar.invalid",
        admin_username="northstar_operator",
        admin_password=SecretStr("local-operator-change-me"),
        admin_email="operator@northstar.invalid",
    )


async def _count(session: AsyncSession, model: type[SQLModel]) -> int:
    return int((await session.exec(select(func.count()).select_from(model))).one())


@pytest.mark.asyncio
async def test_bootstrap_business_records_is_idempotent_and_tenant_owned(db_session) -> None:
    """Running the canonical data reconciliation twice must not duplicate records."""
    config = _config()

    first_customer, first_admin, _ = await bootstrap_business_records(db_session, config)
    second_customer, second_admin, orders = await bootstrap_business_records(db_session, config)

    assert second_customer.id == first_customer.id
    assert second_admin.id == first_admin.id
    assert second_customer.verify_password("local-customer-change-me")
    assert second_admin.verify_password("local-operator-change-me")
    assert second_customer.role == "customer"
    assert second_admin.role == "super_admin"
    assert second_admin.is_admin is True
    assert len(orders) == 4
    assert all(order.user_id == second_customer.id for order in orders)
    assert all(order.tenant_id == config.tenant_id for order in orders)
    assert await _count(db_session, User) == 2
    assert await _count(db_session, Order) == 4
    assert await _count(db_session, RefundApplication) == 1
    assert await _count(db_session, AuditLog) == 1
    assert await _count(db_session, ComplaintTicket) == 1
    assert await _count(db_session, AgentConfig) == 8
    assert await _count(db_session, RoutingRule) == 11
    assert await _count(db_session, OutboxEvent) == 1


@pytest.mark.asyncio
async def test_bootstrap_tenant_registry_uses_admin_connection_path() -> None:
    """Tenant registry reconciliation must not inherit the runtime capability role."""
    config = _config()
    config = LocalBootstrapConfig(
        enabled=config.enabled,
        environment=config.environment,
        tenant_id="bootstrap-admin-path",
        tenant_name="Bootstrap Admin Path",
        customer_username=config.customer_username,
        customer_password=config.customer_password,
        customer_email=config.customer_email,
        admin_username=config.admin_username,
        admin_password=config.admin_password,
        admin_email=config.admin_email,
    )

    await _ensure_tenant(config, settings.MIGRATION_DATABASE_URL)

    engine = create_async_engine(settings.MIGRATION_DATABASE_URL)
    try:
        async with engine.connect() as connection:
            display_name = await connection.scalar(
                select(Tenant.display_name).where(Tenant.id == config.tenant_id)
            )
    finally:
        await engine.dispose()
    assert display_name == config.tenant_name
