"""Behavior tests for crash-recoverable consumer reliability."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import NoReturn

import pytest
from celery.exceptions import Reject, Retry
from pydantic import JsonValue
from sqlmodel import Session, select

from app.core.tenancy import tenant_scope
from app.core.utils import utc_now
from app.models.task_receipt import TaskExecutionReceipt, TaskReceiptStatus
from app.task_runtime.context import build_task_context
from app.task_runtime.dead_letter import DeadLetterMessage
from app.task_runtime.envelope import TaskEnvelope
from app.task_runtime.reliability import (
    PermanentTaskError,
    TransientTaskError,
    consume_db_task,
    execute_db_task_once,
)


@dataclass
class FakeRequest:
    """Minimal Celery request state used at the transport seam."""

    retries: int = 0
    id: str | None = "task-retry-test"


class FakeBoundTask:
    """Represent Celery retry signaling without a broker."""

    def __init__(self, *, max_retries: int = 3) -> None:
        self.request = FakeRequest()
        self.max_retries = max_retries
        self.countdowns: list[int] = []

    def retry(self, *, exc: BaseException, countdown: int) -> NoReturn:
        self.countdowns.append(countdown)
        raise Retry(exc=exc)


class RecordingDeadLetterPublisher:
    """Capture terminal messages at the external broker seam."""

    def __init__(self) -> None:
        self.messages: list[DeadLetterMessage] = []

    def publish(self, message: DeadLetterMessage) -> str:
        self.messages.append(message)
        return "dead-letter-test"


class FailingDeadLetterPublisher:
    """Represent a temporarily unavailable terminal evidence queue."""

    def publish(self, message: DeadLetterMessage) -> str:
        raise ConnectionError("DLQ unavailable")


def test_transient_failure_receipt_is_recoverable_and_later_completes(db_sync_session) -> None:
    """Recover the same logical task after a persisted retryable failure."""
    tenant_id = "tenant-reliable-retry"
    envelope = TaskEnvelope(
        task_context=build_task_context(
            task_name="refund.process_payment",
            tenant_id=tenant_id,
            user_id=41,
            correlation_id="corr-reliable-retry",
            operation_id="refund:41:payment",
        ),
        payload={"refund_id": 41},
    )
    calls = 0

    def operation(_session: Session) -> dict[str, JsonValue]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TransientTaskError("PROVIDER_TIMEOUT", "provider timeout")
        return {"status": "success", "refund_id": 41}

    with tenant_scope(tenant_id):
        try:
            execute_db_task_once(
                session=db_sync_session,
                envelope=envelope,
                handler="refund.process_payment",
                attempt=1,
                operation=operation,
            )
        except TransientTaskError:
            pass
        else:
            raise AssertionError("transient failure must propagate to the retry policy")

        failed_receipt = db_sync_session.exec(
            select(TaskExecutionReceipt).where(
                TaskExecutionReceipt.idempotency_key == envelope.task_context.idempotency_key
            )
        ).one()
        assert failed_receipt.status == TaskReceiptStatus.RETRYABLE
        assert failed_receipt.attempt_count == 1
        assert failed_receipt.failure_code == "PROVIDER_TIMEOUT"

        result = execute_db_task_once(
            session=db_sync_session,
            envelope=envelope,
            handler="refund.process_payment",
            attempt=2,
            operation=operation,
        )

        completed_receipt = db_sync_session.exec(
            select(TaskExecutionReceipt).where(
                TaskExecutionReceipt.receipt_id == failed_receipt.receipt_id
            )
        ).one()
    assert result["status"] == "success"
    assert result["duplicate"] is False
    assert calls == 2
    assert completed_receipt.status == TaskReceiptStatus.COMPLETED
    assert completed_receipt.attempt_count == 2
    assert completed_receipt.last_error is None


def test_stale_processing_receipt_is_reclaimed_after_worker_crash(db_sync_session) -> None:
    """Recover a lease left behind by a worker that stopped before completion."""
    tenant_id = "tenant-receipt-crash-recovery"
    envelope = TaskEnvelope(
        task_context=build_task_context(
            task_name="refund.process_payment",
            tenant_id=tenant_id,
            user_id=45,
            correlation_id="corr-receipt-crash-recovery",
            operation_id="refund:45:payment",
        ),
        payload={"refund_id": 45},
    )
    stale = TaskExecutionReceipt(
        tenant_id=tenant_id,
        handler="refund.process_payment",
        idempotency_key=envelope.task_context.idempotency_key,
        status=TaskReceiptStatus.PROCESSING,
        attempt_count=1,
        claim_expires_at=utc_now() - timedelta(seconds=1),
    )
    db_sync_session.add(stale)
    db_sync_session.commit()

    with tenant_scope(tenant_id):
        result = execute_db_task_once(
            session=db_sync_session,
            envelope=envelope,
            handler="refund.process_payment",
            attempt=2,
            operation=lambda _session: {"status": "success", "refund_id": 45},
        )

    db_sync_session.refresh(stale)
    assert result["status"] == "success"
    assert stale.status == TaskReceiptStatus.COMPLETED
    assert stale.attempt_count == 2
    assert stale.claim_token is None
    assert stale.claim_expires_at is None


def test_consumer_transient_failure_retries_then_succeeds_without_dead_letter(
    db_sync_session,
    tenant_context: str,
) -> None:
    """Retry a transient failure with one stable task identity, then complete."""
    tenant_id = tenant_context
    envelope = TaskEnvelope(
        task_context=build_task_context(
            task_name="refund.process_payment",
            tenant_id=tenant_id,
            user_id=42,
            correlation_id="corr-consumer-retry",
            operation_id="refund:42:payment",
        ),
        payload={"refund_id": 42},
    )
    task = FakeBoundTask(max_retries=3)
    dead_letters = RecordingDeadLetterPublisher()
    calls = 0

    def operation(_session: Session) -> dict[str, JsonValue]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TransientTaskError("PROVIDER_TIMEOUT", "provider timeout")
        return {"status": "success", "refund_id": 42}

    with tenant_scope(tenant_id):
        with pytest.raises(Retry):
            consume_db_task(
                task=task,
                raw_envelope=envelope.to_message(),
                handler="refund.process_payment",
                operation=operation,
                session=db_sync_session,
                dead_letter_publisher=dead_letters,
            )
        task.request.retries = 1
        result = consume_db_task(
            task=task,
            raw_envelope=envelope.to_message(),
            handler="refund.process_payment",
            operation=operation,
            session=db_sync_session,
            dead_letter_publisher=dead_letters,
        )

    assert result["status"] == "success"
    assert calls == 2
    assert len(task.countdowns) == 1
    assert 1 <= task.countdowns[0] <= 10
    assert dead_letters.messages == []


def test_consumer_retry_exhaustion_marks_terminal_and_dead_letters(
    db_sync_session,
    tenant_context: str,
) -> None:
    """Stop bounded transient retries and retain terminal broker evidence."""
    tenant_id = tenant_context
    envelope = TaskEnvelope(
        task_context=build_task_context(
            task_name="refund.process_payment",
            tenant_id=tenant_id,
            user_id=43,
            correlation_id="corr-consumer-exhausted",
            operation_id="refund:43:payment",
        ),
        payload={"refund_id": 43},
    )
    task = FakeBoundTask(max_retries=1)
    task.request.retries = 1
    dead_letters = RecordingDeadLetterPublisher()

    def operation(_session: Session) -> dict[str, JsonValue]:
        raise TransientTaskError("PROVIDER_UNAVAILABLE", "provider unavailable")

    with tenant_scope(tenant_id):
        result = consume_db_task(
            task=task,
            raw_envelope=envelope.to_message(),
            handler="refund.process_payment",
            operation=operation,
            session=db_sync_session,
            dead_letter_publisher=dead_letters,
        )
        receipt = db_sync_session.exec(
            select(TaskExecutionReceipt).where(
                TaskExecutionReceipt.idempotency_key == envelope.task_context.idempotency_key
            )
        ).one()

    assert result["status"] == "dead_lettered"
    assert receipt.status == TaskReceiptStatus.TERMINAL
    assert receipt.attempt_count == 2
    assert len(dead_letters.messages) == 1
    terminal = dead_letters.messages[0]
    assert terminal.tenant_id == tenant_id
    assert terminal.idempotency_key == envelope.task_context.idempotency_key
    assert terminal.correlation_id == "corr-consumer-exhausted"
    assert terminal.attempt == 2
    assert terminal.failure_code == "PROVIDER_UNAVAILABLE"
    assert terminal.envelope == envelope.model_dump(mode="json")


def test_consumer_permanent_failure_dead_letters_without_retry(
    db_sync_session,
    tenant_context: str,
) -> None:
    """Fail closed without looping and redact terminal failure details."""
    tenant_id = tenant_context
    raw_phone = "13800138000"
    envelope = TaskEnvelope(
        task_context=build_task_context(
            task_name="refund.process_payment",
            tenant_id=tenant_id,
            user_id=44,
            correlation_id="corr-consumer-permanent",
            operation_id="refund:44:payment",
        ),
        payload={"refund_id": 44},
    )
    task = FakeBoundTask(max_retries=3)
    dead_letters = RecordingDeadLetterPublisher()

    def operation(_session: Session) -> dict[str, JsonValue]:
        raise PermanentTaskError("INVALID_BUSINESS_STATE", f"invalid recipient {raw_phone}")

    with tenant_scope(tenant_id):
        result = consume_db_task(
            task=task,
            raw_envelope=envelope.to_message(),
            handler="refund.process_payment",
            operation=operation,
            session=db_sync_session,
            dead_letter_publisher=dead_letters,
        )
        receipt = db_sync_session.exec(
            select(TaskExecutionReceipt).where(
                TaskExecutionReceipt.idempotency_key == envelope.task_context.idempotency_key
            )
        ).one()

    assert result["status"] == "dead_lettered"
    assert task.countdowns == []
    assert receipt.status == TaskReceiptStatus.TERMINAL
    assert len(dead_letters.messages) == 1
    terminal = dead_letters.messages[0]
    assert terminal.failure_code == "INVALID_BUSINESS_STATE"
    assert raw_phone not in terminal.failure_reason


def test_consumer_invalid_envelope_dead_letters_without_untrusted_payload(
    db_sync_session,
) -> None:
    """Reject malformed broker input before effects and omit its raw PII."""
    raw_phone = "13800138000"
    task = FakeBoundTask(max_retries=3)
    dead_letters = RecordingDeadLetterPublisher()
    called = False

    def operation(_session: Session) -> dict[str, JsonValue]:
        nonlocal called
        called = True
        return {"status": "success"}

    result = consume_db_task(
        task=task,
        raw_envelope={"payload": {"phone": raw_phone}},
        handler="refund.process_payment",
        operation=operation,
        session=db_sync_session,
        dead_letter_publisher=dead_letters,
    )

    assert result["status"] == "dead_lettered"
    assert result["failure_code"] == "INVALID_ENVELOPE"
    assert called is False
    assert task.countdowns == []
    assert len(dead_letters.messages) == 1
    terminal = dead_letters.messages[0]
    assert terminal.tenant_id is None
    assert terminal.idempotency_key is None
    assert terminal.envelope is None
    assert raw_phone not in terminal.model_dump_json()


def test_dead_letter_publish_failure_requeues_original_delivery(db_sync_session) -> None:
    """Keep terminal work recoverable when the RabbitMQ DLQ cannot be reached."""
    task = FakeBoundTask(max_retries=0)

    with pytest.raises(Reject) as rejected:
        consume_db_task(
            task=task,
            raw_envelope={"payload": {"unexpected": True}},
            handler="refund.process_payment",
            operation=lambda _session: {"status": "must-not-run"},
            session=db_sync_session,
            dead_letter_publisher=FailingDeadLetterPublisher(),
        )

    assert rejected.value.requeue is True
