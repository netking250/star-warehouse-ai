"""Transactional outbox enqueue behavior."""

import pytest
from sqlmodel import select

from app.core.database import async_session_maker
from app.core.tenancy import TenantIsolationError, tenant_scope
from app.models.outbox import OutboxEvent
from app.outbox import enqueue_task
from app.task_runtime.context import build_task_context


@pytest.mark.asyncio
async def test_enqueue_task_caller_rollback_removes_outbox_event() -> None:
    """Keep outbox persistence inside the caller-owned transaction."""
    with tenant_scope("tenant-outbox-rollback"):
        task_context = build_task_context(
            task_name="refund.notify_admin",
            tenant_id="tenant-outbox-rollback",
            user_id=101,
            correlation_id="corr-outbox-rollback",
            operation_id="audit:301:notify",
        )
        async with async_session_maker() as session:
            event = await enqueue_task(
                session=session,
                task_name="refund.notify_admin",
                task_context=task_context,
                payload={"audit_log_id": 301},
                event_type="refund.audit_requested",
                aggregate_type="audit_log",
                aggregate_id="301",
            )
            event_id = event.event_id
            await session.flush()
            await session.rollback()

        async with async_session_maker() as verification_session:
            result = await verification_session.exec(
                select(OutboxEvent).where(OutboxEvent.event_id == event_id)
            )

    assert result.one_or_none() is None


@pytest.mark.asyncio
async def test_enqueue_task_rejects_cross_tenant_context() -> None:
    """Fail closed when the durable tenant differs from the transaction scope."""
    with tenant_scope("tenant-active"):
        task_context = build_task_context(
            task_name="refund.notify_admin",
            tenant_id="tenant-other",
            user_id=101,
            correlation_id="corr-cross-tenant",
        )
        async with async_session_maker() as session:
            with pytest.raises(TenantIsolationError):
                await enqueue_task(
                    session=session,
                    task_name="refund.notify_admin",
                    task_context=task_context,
                    payload={"audit_log_id": 301},
                    event_type="refund.audit_requested",
                    aggregate_type="audit_log",
                    aggregate_id="301",
                )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"phone": "13800138000"},
        {"recipient": "buyer@example.com"},
        {"question": "please refund the order"},
    ],
)
async def test_enqueue_task_rejects_raw_pii_and_request_text(payload) -> None:
    """Prevent raw contact data and original questions entering the outbox."""
    with tenant_scope("tenant-pii-guard"):
        task_context = build_task_context(
            task_name="refund.notify_admin",
            tenant_id="tenant-pii-guard",
            user_id=101,
            correlation_id="corr-pii-guard",
        )
        async with async_session_maker() as session:
            with pytest.raises(ValueError, match="Outbox payload"):
                await enqueue_task(
                    session=session,
                    task_name="refund.notify_admin",
                    task_context=task_context,
                    payload=payload,
                    event_type="refund.audit_requested",
                    aggregate_type="audit_log",
                    aggregate_id="301",
                )
