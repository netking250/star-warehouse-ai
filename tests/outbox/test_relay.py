"""Outbox relay behavior across the database and publisher seam."""

from __future__ import annotations

import asyncio
import uuid
from datetime import timedelta

import pytest
from sqlmodel import select

from app.core.database import async_session_maker
from app.core.tenancy import tenant_scope
from app.core.utils import utc_now
from app.models.outbox import OutboxEvent, OutboxStatus
from app.outbox import OutboxRelay, enqueue_task
from app.task_runtime.context import build_task_context
from app.task_runtime.envelope import TaskEnvelope


class RecordingPublisher:
    """Capture broker-bound messages at the publisher Port."""

    def __init__(self) -> None:
        self.messages: list[tuple[str, TaskEnvelope, uuid.UUID]] = []

    async def publish(self, *, task_name: str, envelope: TaskEnvelope, task_id: uuid.UUID) -> str:
        self.messages.append((task_name, envelope, task_id))
        return str(task_id)


class FailingPublisher:
    """Represent a temporarily unavailable broker."""

    async def publish(self, *, task_name: str, envelope: TaskEnvelope, task_id: uuid.UUID) -> str:
        raise ConnectionError("broker unavailable")


class BlockingPublisher(RecordingPublisher):
    """Hold publication open so a second relay can attempt a claim."""

    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def publish(self, *, task_name: str, envelope: TaskEnvelope, task_id: uuid.UUID) -> str:
        self.started.set()
        await self.release.wait()
        return await super().publish(task_name=task_name, envelope=envelope, task_id=task_id)


class SuccessfulThenCrashPublisher(RecordingPublisher):
    """Simulate process death after broker success and before database marking."""

    async def publish(self, *, task_name: str, envelope: TaskEnvelope, task_id: uuid.UUID) -> str:
        published_id = await super().publish(
            task_name=task_name, envelope=envelope, task_id=task_id
        )
        current_task = asyncio.current_task()
        assert current_task is not None
        asyncio.get_running_loop().call_soon(current_task.cancel)
        return published_id


async def _committed_event(*, tenant_id: str, operation_id: str) -> uuid.UUID:
    with tenant_scope(tenant_id):
        context = build_task_context(
            task_name="refund.notify_admin",
            tenant_id=tenant_id,
            user_id=202,
            correlation_id=f"corr:{operation_id}",
            operation_id=operation_id,
        )
        async with async_session_maker() as session:
            event = await enqueue_task(
                session=session,
                task_name="refund.notify_admin",
                task_context=context,
                payload={"audit_log_id": 402},
                event_type="refund.audit_requested",
                aggregate_type="audit_log",
                aggregate_id="402",
            )
            await session.commit()
            return event.event_id


@pytest.mark.asyncio
async def test_relay_committed_pending_event_is_published_and_marked() -> None:
    """Recover a committed intent and mark it only after publication."""
    with tenant_scope("tenant-relay-recovery"):
        context = build_task_context(
            task_name="refund.notify_admin",
            tenant_id="tenant-relay-recovery",
            user_id=202,
            correlation_id="corr-relay-recovery",
            operation_id="audit:402:notify",
        )
        async with async_session_maker() as session:
            event = await enqueue_task(
                session=session,
                task_name="refund.notify_admin",
                task_context=context,
                payload={"audit_log_id": 402},
                event_type="refund.audit_requested",
                aggregate_type="audit_log",
                aggregate_id="402",
            )
            event_id = event.event_id
            await session.commit()

    publisher = RecordingPublisher()
    result = await OutboxRelay(publisher=publisher).run_once()

    assert result.claimed == 1
    assert result.published == 1
    assert result.failed == 0
    assert publisher.messages[0][0] == "refund.notify_admin"
    assert publisher.messages[0][1].task_context.tenant_id == "tenant-relay-recovery"
    assert publisher.messages[0][2] == event_id

    async with async_session_maker() as session:
        stored = (
            await session.exec(select(OutboxEvent).where(OutboxEvent.event_id == event_id))
        ).one()
    assert stored.status == OutboxStatus.PUBLISHED
    assert stored.published_at is not None


@pytest.mark.asyncio
async def test_relay_publisher_failure_keeps_event_retryable() -> None:
    """Record a failed attempt without losing the pending event."""
    event_id = await _committed_event(
        tenant_id="tenant-relay-failure", operation_id="audit:403:notify"
    )
    before_attempt = utc_now()

    result = await OutboxRelay(publisher=FailingPublisher(), retry_base_seconds=7).run_once()

    assert result.claimed == 1
    assert result.published == 0
    assert result.failed == 1
    async with async_session_maker() as session:
        stored = (
            await session.exec(select(OutboxEvent).where(OutboxEvent.event_id == event_id))
        ).one()
    assert stored.status == OutboxStatus.PENDING
    assert stored.attempt_count == 1
    assert stored.last_error == "ConnectionError: broker unavailable"
    assert stored.available_at > before_attempt + timedelta(seconds=6)
    assert stored.published_at is None


@pytest.mark.asyncio
async def test_relay_active_lease_prevents_concurrent_duplicate_claim() -> None:
    """Prevent two relay replicas from publishing the same active lease."""
    event_id = await _committed_event(
        tenant_id="tenant-relay-concurrent", operation_id="audit:404:notify"
    )
    publisher = BlockingPublisher()
    first_relay = OutboxRelay(publisher=publisher, lease_seconds=30)
    second_relay = OutboxRelay(publisher=RecordingPublisher(), lease_seconds=30)

    first_run = asyncio.create_task(first_relay.run_once())
    await asyncio.wait_for(publisher.started.wait(), timeout=2)
    second_result = await second_relay.run_once()
    publisher.release.set()
    first_result = await first_run

    assert first_result.published == 1
    assert second_result.claimed == 0
    assert [message[2] for message in publisher.messages] == [event_id]


@pytest.mark.asyncio
async def test_relay_expired_lease_is_recovered_with_same_idempotency_key() -> None:
    """Republish an abandoned claim without changing its dedupe identity."""
    event_id = await _committed_event(
        tenant_id="tenant-relay-expired", operation_id="audit:405:notify"
    )
    async with async_session_maker() as session:
        event = (
            await session.exec(select(OutboxEvent).where(OutboxEvent.event_id == event_id))
        ).one()
        original_idempotency_key = event.idempotency_key
        event.status = OutboxStatus.PUBLISHING
        event.claim_token = uuid.uuid4()
        event.claim_expires_at = utc_now() - timedelta(seconds=1)
        event.attempt_count = 1
        session.add(event)
        await session.commit()

    publisher = RecordingPublisher()
    result = await OutboxRelay(publisher=publisher).run_once()

    assert result.published == 1
    assert publisher.messages[0][1].task_context.idempotency_key == original_idempotency_key
    async with async_session_maker() as session:
        stored = (
            await session.exec(select(OutboxEvent).where(OutboxEvent.event_id == event_id))
        ).one()
    assert stored.attempt_count == 2
    assert stored.status == OutboxStatus.PUBLISHED


@pytest.mark.asyncio
async def test_relay_publish_success_then_crash_remains_recoverable_but_may_duplicate() -> None:
    """Preserve at-least-once semantics across the unavoidable mark-success window."""
    event_id = await _committed_event(
        tenant_id="tenant-relay-crash-window", operation_id="audit:406:notify"
    )
    first_publisher = SuccessfulThenCrashPublisher()

    with pytest.raises(asyncio.CancelledError):
        await OutboxRelay(publisher=first_publisher, lease_seconds=30).run_once()

    assert [message[2] for message in first_publisher.messages] == [event_id]
    original_key = first_publisher.messages[0][1].task_context.idempotency_key
    async with async_session_maker() as session:
        stored = (
            await session.exec(select(OutboxEvent).where(OutboxEvent.event_id == event_id))
        ).one()
        assert stored.status == OutboxStatus.PUBLISHING
        assert stored.published_at is None
        stored.claim_expires_at = utc_now() - timedelta(seconds=1)
        session.add(stored)
        await session.commit()

    retry_publisher = RecordingPublisher()
    result = await OutboxRelay(publisher=retry_publisher).run_once()

    assert result.published == 1
    assert retry_publisher.messages[0][1].task_context.idempotency_key == original_key
