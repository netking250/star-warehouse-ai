"""PostgreSQL integration coverage for the canonical local bootstrap dataset."""

import pytest
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import col, select

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
from app.task_runtime.context import build_task_context


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


@pytest.mark.asyncio
async def test_bootstrap_business_records_is_idempotent_and_tenant_owned(db_session) -> None:
    """Running the canonical data reconciliation twice must not duplicate records."""
    config = _config()
    unrelated_user = User(
        tenant_id=config.tenant_id,
        username="unrelated-bootstrap-test-user",
        password_hash="unused-test-hash",
        email="unrelated-bootstrap-test@northstar.invalid",
        full_name="Unrelated Test User",
    )
    db_session.add(unrelated_user)
    await db_session.flush()

    first_customer, first_admin, first_orders = await bootstrap_business_records(db_session, config)
    first_order_ids = {order.order_sn: order.id for order in first_orders}
    second_customer, second_admin, orders = await bootstrap_business_records(db_session, config)

    expected_order_sns = {
        "UAT-NO-2026092201",
        "UAT-NO-2026092202",
        "UAT-NO-2026092203",
        "UAT-NO-2026092204",
    }
    expected_agent_names = {
        "policy_agent",
        "order_agent",
        "product",
        "cart",
        "logistics",
        "account",
        "payment",
        "complaint",
    }
    expected_routes = {
        ("ORDER", "order_agent"),
        ("AFTER_SALES", "order_agent"),
        ("POLICY", "policy_agent"),
        ("LOGISTICS", "logistics"),
        ("ACCOUNT", "account"),
        ("PAYMENT", "payment"),
        ("PRODUCT", "product"),
        ("CART", "cart"),
        ("PROMOTION", "policy_agent"),
        ("COMPLAINT", "complaint"),
        ("OTHER", "policy_agent"),
    }

    assert second_customer.id == first_customer.id
    assert second_admin.id == first_admin.id
    assert second_customer.verify_password("local-customer-change-me")
    assert second_admin.verify_password("local-operator-change-me")
    assert second_customer.role == "customer"
    assert second_admin.role == "super_admin"
    assert second_admin.is_admin is True
    assert (
        await db_session.exec(select(User.id).where(User.username == unrelated_user.username))
    ).one() == unrelated_user.id

    accounts = (
        await db_session.exec(
            select(User).where(
                User.tenant_id == config.tenant_id,
                col(User.username).in_({config.customer_username, config.admin_username}),
            )
        )
    ).all()
    assert len(accounts) == 2
    assert {user.username for user in accounts} == {
        config.customer_username,
        config.admin_username,
    }
    assert {user.id for user in accounts} == {second_customer.id, second_admin.id}

    assert len(orders) == len(expected_order_sns)
    assert set(first_order_ids) == expected_order_sns
    assert {order.order_sn: order.id for order in orders} == first_order_ids
    persisted_orders = (
        await db_session.exec(
            select(Order).where(
                Order.tenant_id == config.tenant_id,
                col(Order.order_sn).in_(expected_order_sns),
            )
        )
    ).all()
    assert len(persisted_orders) == len(expected_order_sns)
    assert {order.order_sn: order.id for order in persisted_orders} == first_order_ids
    assert all(order.user_id == second_customer.id for order in persisted_orders)
    refundable_order_id = first_order_ids["UAT-NO-2026092201"]

    refunds = (
        await db_session.exec(
            select(RefundApplication).where(
                RefundApplication.tenant_id == config.tenant_id,
                RefundApplication.order_id == refundable_order_id,
                RefundApplication.user_id == second_customer.id,
            )
        )
    ).all()
    assert len(refunds) == 1

    audits = (
        await db_session.exec(
            select(AuditLog).where(
                AuditLog.tenant_id == config.tenant_id,
                AuditLog.thread_id == "uat-refund-approval-20260922",
            )
        )
    ).all()
    assert len(audits) == 1
    audit = audits[0]
    assert audit.user_id == second_customer.id
    assert audit.order_id == refundable_order_id
    assert audit.refund_application_id == refunds[0].id
    assert audit.id is not None
    assert second_admin.id is not None

    complaints = (
        await db_session.exec(
            select(ComplaintTicket).where(
                ComplaintTicket.tenant_id == config.tenant_id,
                ComplaintTicket.thread_id == "uat-logistics-complaint-20260922",
            )
        )
    ).all()
    assert len(complaints) == 1
    assert complaints[0].user_id == second_customer.id
    assert complaints[0].order_sn == "UAT-NO-2026092203"
    assert complaints[0].assigned_to == second_admin.id

    agent_configs = (
        await db_session.exec(
            select(AgentConfig).where(
                AgentConfig.tenant_id == config.tenant_id,
                col(AgentConfig.agent_name).in_(expected_agent_names),
            )
        )
    ).all()
    assert len(agent_configs) == len(expected_agent_names)
    assert {agent.agent_name for agent in agent_configs} == expected_agent_names

    tenant_routes = (
        await db_session.exec(select(RoutingRule).where(RoutingRule.tenant_id == config.tenant_id))
    ).all()
    bootstrap_routes = [
        rule
        for rule in tenant_routes
        if (rule.intent_category, rule.target_agent) in expected_routes
    ]
    assert len(bootstrap_routes) == len(expected_routes)
    assert {
        (rule.intent_category, rule.target_agent) for rule in bootstrap_routes
    } == expected_routes

    notification_context = build_task_context(
        task_name="refund.notify_admin",
        tenant_id=config.tenant_id,
        user_id=second_admin.id,
        correlation_id="local-bootstrap:refund-review",
        operation_id=f"audit:{audit.id}:notify",
    )
    outbox_events = (
        await db_session.exec(
            select(OutboxEvent).where(
                OutboxEvent.tenant_id == config.tenant_id,
                OutboxEvent.event_type == "local_bootstrap.refund_review_notification",
                OutboxEvent.aggregate_type == "audit_log",
                OutboxEvent.aggregate_id == str(audit.id),
                OutboxEvent.idempotency_key == notification_context.idempotency_key,
            )
        )
    ).all()
    assert len(outbox_events) == 1
    assert outbox_events[0].task_name == "refund.notify_admin"


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
