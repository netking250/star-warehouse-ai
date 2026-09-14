"""Real RabbitMQ integration tests for reliable task delivery."""

from __future__ import annotations

import asyncio
import os
import threading
import uuid

import pytest
from celery.contrib.testing.worker import start_worker
from celery.signals import task_postrun
from kombu import Connection
from sqlmodel import col, func, select

from app.core.database import async_session_maker
from app.core.tenancy import tenant_scope
from app.models.audit import AuditLog, RiskLevel
from app.models.message import MessageCard
from app.models.outbox import OutboxEvent, OutboxStatus
from app.models.task_receipt import TaskExecutionReceipt, TaskReceiptStatus
from app.models.user import User
from app.outbox import CeleryTaskPublisher, OutboxRelay, enqueue_task
from app.task_runtime.context import build_task_context
from app.task_runtime.dead_letter import CeleryDeadLetterPublisher, DeadLetterMessage
from app.task_runtime.envelope import TaskEnvelope


def _rabbitmq_url() -> str:
    url = os.environ.get("T04_RABBITMQ_URL")
    if not url:
        pytest.skip("T04_RABBITMQ_URL is required for real RabbitMQ integration")
    return url


@pytest.mark.rabbitmq
def test_rabbitmq_unacked_delivery_returns_to_replacement_consumer() -> None:
    """Redeliver a message after simulated worker loss before safe ACK."""
    broker_url = _rabbitmq_url()
    queue_name = f"t04.redelivery.{uuid.uuid4().hex}"
    payload = {"task_id": str(uuid.uuid4()), "identity": "redelivery-probe"}

    with Connection(broker_url) as first_connection:
        queue = first_connection.SimpleQueue(queue_name, no_ack=False)
        queue.put(payload, serializer="json", delivery_mode=2)
        first_delivery = queue.get(block=True, timeout=5)
        assert first_delivery.payload == payload
        # Closing the connection without ACK simulates abrupt worker loss.

    with Connection(broker_url) as replacement_connection:
        replacement_queue = replacement_connection.SimpleQueue(queue_name, no_ack=False)
        redelivery = replacement_queue.get(block=True, timeout=5)
        try:
            assert redelivery.payload == payload
            assert redelivery.delivery_info.get("redelivered") is True
            redelivery.ack()
        finally:
            replacement_queue.close()
            replacement_queue.queue.delete()


@pytest.mark.rabbitmq
def test_terminal_message_is_persisted_in_rabbitmq_dead_letter_queue() -> None:
    """Publish enriched terminal evidence into the real isolated DLQ."""
    broker_url = _rabbitmq_url()
    from app.celery_app import celery_app

    queue_definition = celery_app.amqp.queues["critical.dlq"]
    with Connection(broker_url) as connection:
        bound_queue = queue_definition.bind(connection.default_channel)
        bound_queue.declare()
        bound_queue.purge()

    terminal = DeadLetterMessage(
        task_id=str(uuid.uuid4()),
        task_name="refund.process_payment",
        tenant_id="tenant-rabbit-dlq",
        idempotency_key="refund.process_payment:v1:dead-letter",
        correlation_id="corr-rabbit-dlq",
        attempt=4,
        failure_code="PROVIDER_UNAVAILABLE",
        failure_reason="provider unavailable",
        envelope={"schema_version": 1},
    )
    CeleryDeadLetterPublisher(celery_app, broker_url=broker_url).publish(terminal)

    with Connection(broker_url) as connection:
        bound_queue = queue_definition.bind(connection.default_channel)
        delivery = bound_queue.get(no_ack=False)
        assert delivery is not None
        try:
            assert delivery.payload == terminal.model_dump(mode="json")
            delivery.ack()
        finally:
            bound_queue.purge()


@pytest.mark.rabbitmq
@pytest.mark.asyncio
async def test_outbox_rabbitmq_worker_duplicate_delivery_applies_effect_once() -> None:
    """Relay a real outbox event and deduplicate a second RabbitMQ delivery."""
    broker_url = _rabbitmq_url()
    tenant_id = f"tenant-rabbit-e2e-{uuid.uuid4().hex[:8]}"
    correlation_id = f"corr-rabbit-e2e-{uuid.uuid4().hex}"

    from app.celery_app import celery_app

    assert celery_app.conf.broker_url == broker_url
    celery_app.loader.import_default_modules()
    celery_app.conf.task_ignore_result = True

    with tenant_scope(tenant_id):
        async with async_session_maker() as session:
            user = User(
                tenant_id=tenant_id,
                username=f"rabbit-{uuid.uuid4().hex}",
                password_hash="integration-test-hash",
                email=f"rabbit-{uuid.uuid4().hex}@example.invalid",
                full_name="Rabbit Integration",
            )
            session.add(user)
            await session.flush()
            assert user.id is not None
            audit = AuditLog(
                tenant_id=tenant_id,
                thread_id=f"thread-{uuid.uuid4().hex}",
                user_id=user.id,
                trigger_reason="T04 broker integration",
                risk_level=RiskLevel.HIGH,
                context_snapshot={},
            )
            session.add(audit)
            await session.flush()
            assert audit.id is not None
            context = build_task_context(
                task_name="refund.notify_admin",
                tenant_id=tenant_id,
                user_id=user.id,
                correlation_id=correlation_id,
                thread_id=audit.thread_id,
                operation_id=f"audit:{audit.id}:notify",
            )
            event = await enqueue_task(
                session=session,
                task_name="refund.notify_admin",
                task_context=context,
                payload={"audit_log_id": audit.id},
                event_type="refund.audit_requested",
                aggregate_type="audit_log",
                aggregate_id=str(audit.id),
            )
            event_id = event.event_id
            envelope = TaskEnvelope.from_message(event.envelope)
            await session.commit()

    publisher = CeleryTaskPublisher(celery_app)
    with start_worker(
        celery_app,
        perform_ping_check=False,
        pool="solo",
        concurrency=1,
        queues=["critical"],
        loglevel="WARNING",
    ):
        relay_result = await OutboxRelay(publisher=publisher).run_once()
        assert relay_result.published == 1
        await _wait_for_completed_receipt(
            tenant_id=tenant_id,
            idempotency_key=context.idempotency_key,
        )

        duplicate_task_id = uuid.uuid4()
        duplicate_finished = threading.Event()

        def observe_duplicate(*, task_id: str | None = None, **_kwargs: object) -> None:
            if task_id == str(duplicate_task_id):
                duplicate_finished.set()

        task_postrun.connect(observe_duplicate, weak=False)
        await publisher.publish(
            task_name="refund.notify_admin",
            envelope=envelope,
            task_id=duplicate_task_id,
        )
        try:
            assert await asyncio.to_thread(duplicate_finished.wait, 10)
        finally:
            task_postrun.disconnect(observe_duplicate)

    with tenant_scope(tenant_id):
        async with async_session_maker() as session:
            effect_count = (
                await session.exec(
                    select(func.count(col(MessageCard.id))).where(
                        col(MessageCard.thread_id) == audit.thread_id
                    )
                )
            ).one()
            stored_event = (
                await session.exec(select(OutboxEvent).where(OutboxEvent.event_id == event_id))
            ).one()
            receipt_count = (
                await session.exec(
                    select(func.count(col(TaskExecutionReceipt.receipt_id))).where(
                        col(TaskExecutionReceipt.tenant_id) == tenant_id,
                        col(TaskExecutionReceipt.handler) == "refund.notify_admin",
                        col(TaskExecutionReceipt.idempotency_key) == context.idempotency_key,
                    )
                )
            ).one()
    assert effect_count == 1
    assert receipt_count == 1
    assert stored_event.status == OutboxStatus.PUBLISHED


async def _wait_for_completed_receipt(*, tenant_id: str, idempotency_key: str) -> None:
    for _ in range(100):
        async with async_session_maker() as session:
            receipt = (
                await session.exec(
                    select(TaskExecutionReceipt).where(
                        col(TaskExecutionReceipt.tenant_id) == tenant_id,
                        col(TaskExecutionReceipt.handler) == "refund.notify_admin",
                        col(TaskExecutionReceipt.idempotency_key) == idempotency_key,
                    )
                )
            ).one_or_none()
        if receipt is not None and receipt.status == TaskReceiptStatus.COMPLETED:
            return
        await asyncio.sleep(0.1)
    raise AssertionError("RabbitMQ worker did not complete the outbox task")
