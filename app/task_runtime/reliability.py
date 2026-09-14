"""Crash-recoverable consumer idempotency for database-local task effects."""

from __future__ import annotations

import hashlib
import logging
import uuid
from collections.abc import Callable, Mapping
from datetime import timedelta
from typing import NoReturn, Protocol

from celery.exceptions import Reject
from pydantic import JsonValue, ValidationError
from sqlalchemy import func
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, col, select

from app.context.pii_filter import pii_filter
from app.core.tenancy import TenantIsolationError
from app.core.utils import utc_now
from app.models.task_receipt import TaskExecutionReceipt, TaskReceiptStatus
from app.observability.metrics import record_task_consumer
from app.task_runtime.binding import task_execution_scope
from app.task_runtime.dead_letter import DeadLetterMessage, DeadLetterPublisher
from app.task_runtime.envelope import TaskEnvelope

TaskResult = dict[str, JsonValue]
DatabaseTaskHandler = Callable[[Session], TaskResult]
ExternalTaskHandler = Callable[[], TaskResult]
logger = logging.getLogger(__name__)


class TaskReceiptInProgressError(RuntimeError):
    """Raised when another worker still owns an unexpired receipt lease."""


class ClassifiedTaskError(RuntimeError):
    """Base error carrying a stable low-cardinality failure code."""

    transient: bool = False

    def __init__(self, failure_code: str, message: str) -> None:
        super().__init__(message)
        self.failure_code = failure_code


class TransientTaskError(ClassifiedTaskError):
    """Failure that may succeed when retried with bounded backoff."""

    transient = True


class PermanentTaskError(ClassifiedTaskError):
    """Failure that must not enter an automatic retry loop."""


class TaskRequest(Protocol):
    """Celery request metadata used by the reliability seam."""

    retries: int
    id: str | None


class BoundRetryTask(Protocol):
    """Minimal bound-task interface required for retry signaling."""

    request: TaskRequest
    max_retries: int | None

    def retry(self, *, exc: BaseException, countdown: int) -> NoReturn:
        """Schedule a replacement delivery and stop the current attempt."""
        ...


def _advisory_lock_key(tenant_id: str, handler: str, idempotency_key: str) -> int:
    identity = f"{tenant_id}\x1f{handler}\x1f{idempotency_key}".encode()
    raw = int.from_bytes(hashlib.sha256(identity).digest()[:8], byteorder="big", signed=False)
    return raw if raw < 2**63 else raw - 2**64


def _retry_delay(*, retry_index: int, idempotency_key: str) -> int:
    exponential = min(2 ** max(retry_index, 0), 300)
    digest = hashlib.sha256(f"{idempotency_key}:{retry_index}".encode()).digest()
    jitter = int.from_bytes(digest[:2], byteorder="big") % max(exponential, 1)
    return min(exponential + jitter, 300)


def consume_db_task(
    *,
    task: BoundRetryTask,
    raw_envelope: Mapping[str, object],
    handler: str,
    operation: DatabaseTaskHandler,
    session: Session,
    dead_letter_publisher: DeadLetterPublisher,
) -> TaskResult:
    """Validate, deduplicate, retry, or dead-letter one database-local task."""
    return _consume_task(
        task=task,
        raw_envelope=raw_envelope,
        handler=handler,
        execute=lambda envelope, attempt: execute_db_task_once(
            session=session,
            envelope=envelope,
            handler=handler,
            attempt=attempt,
            operation=operation,
        ),
        session=session,
        dead_letter_publisher=dead_letter_publisher,
    )


def consume_external_task(
    *,
    task: BoundRetryTask,
    raw_envelope: Mapping[str, object],
    handler: str,
    operation: ExternalTaskHandler,
    session: Session,
    dead_letter_publisher: DeadLetterPublisher,
) -> TaskResult:
    """Run an idempotent external projection behind the shared receipt policy.

    The receipt claim is committed before the external call so no database
    transaction is held while waiting on the provider. Recovery is safe only
    when ``operation`` uses a stable provider identity, as memory vector sync
    does. A crash after the provider succeeds can repeat the operation after
    the lease expires; it must therefore remain idempotent.
    """
    return _consume_task(
        task=task,
        raw_envelope=raw_envelope,
        handler=handler,
        execute=lambda envelope, attempt: execute_external_task_once(
            session=session,
            envelope=envelope,
            handler=handler,
            attempt=attempt,
            operation=operation,
        ),
        session=session,
        dead_letter_publisher=dead_letter_publisher,
    )


def _consume_task(
    *,
    task: BoundRetryTask,
    raw_envelope: Mapping[str, object],
    handler: str,
    execute: Callable[[TaskEnvelope, int], TaskResult],
    session: Session,
    dead_letter_publisher: DeadLetterPublisher,
) -> TaskResult:
    """Apply the common validation, retry, and terminal-failure policy."""
    attempt = task.request.retries + 1
    record_task_consumer(task_type=handler, outcome="received")
    try:
        envelope = TaskEnvelope.from_message(raw_envelope)
    except ValidationError:
        _publish_dead_letter_message(
            publisher=dead_letter_publisher,
            message=DeadLetterMessage(
                task_id=task.request.id,
                task_name=handler,
                attempt=attempt,
                failure_code="INVALID_ENVELOPE",
                failure_reason="Task envelope validation failed",
            ),
            log_fields={"task_id": task.request.id, "task_type": handler, "attempt": attempt},
        )
        record_task_consumer(task_type=handler, outcome="terminal")
        return {
            "status": "dead_lettered",
            "failure_code": "INVALID_ENVELOPE",
            "duplicate": False,
        }
    with task_execution_scope(
        envelope.task_context,
        task_name=f"celery.{handler}",
        task_id=task.request.id,
    ):
        try:
            result = execute(envelope, attempt)
            outcome = "duplicate" if result.get("duplicate") else "succeeded"
            record_task_consumer(task_type=handler, outcome=outcome)
            return result
        except TaskReceiptInProgressError:
            logger.info(
                "Protected task duplicate is already processing",
                extra=_log_fields(task, envelope, handler, attempt),
            )
            record_task_consumer(task_type=handler, outcome="duplicate")
            return {"status": "processing", "duplicate": True}
        except TransientTaskError as error:
            return _retry_or_dead_letter(
                task=task,
                envelope=envelope,
                handler=handler,
                attempt=attempt,
                error=error,
                session=session,
                publisher=dead_letter_publisher,
            )
        except PermanentTaskError as error:
            _publish_dead_letter(
                task=task,
                envelope=envelope,
                handler=handler,
                attempt=attempt,
                error=error,
                publisher=dead_letter_publisher,
            )
            logger.warning(
                "Protected task reached terminal failure",
                extra={
                    **_log_fields(task, envelope, handler, attempt),
                    "failure_code": error.failure_code,
                },
            )
            record_task_consumer(task_type=handler, outcome="terminal")
            return {
                "status": "dead_lettered",
                "failure_code": error.failure_code,
                "duplicate": False,
            }
        except (TimeoutError, ConnectionError, OperationalError) as error:
            classified = TransientTaskError(type(error).__name__.upper(), str(error))
            _record_failure(
                session=session,
                envelope=envelope,
                handler=handler,
                attempt=attempt,
                error=classified,
            )
            return _retry_or_dead_letter(
                task=task,
                envelope=envelope,
                handler=handler,
                attempt=attempt,
                error=classified,
                session=session,
                publisher=dead_letter_publisher,
            )
        except (ValidationError, TenantIsolationError, ValueError) as error:
            classified = PermanentTaskError("INVALID_TASK", type(error).__name__)
            _record_failure(
                session=session,
                envelope=envelope,
                handler=handler,
                attempt=attempt,
                error=classified,
            )
            _publish_dead_letter(
                task=task,
                envelope=envelope,
                handler=handler,
                attempt=attempt,
                error=classified,
                publisher=dead_letter_publisher,
            )
            record_task_consumer(task_type=handler, outcome="terminal")
            return {
                "status": "dead_lettered",
                "failure_code": classified.failure_code,
                "duplicate": False,
            }
        except Exception as error:
            classified = PermanentTaskError("UNEXPECTED_TASK_FAILURE", type(error).__name__)
            _record_failure(
                session=session,
                envelope=envelope,
                handler=handler,
                attempt=attempt,
                error=classified,
            )
            _publish_dead_letter(
                task=task,
                envelope=envelope,
                handler=handler,
                attempt=attempt,
                error=classified,
                publisher=dead_letter_publisher,
            )
            record_task_consumer(task_type=handler, outcome="terminal")
            return {
                "status": "dead_lettered",
                "failure_code": classified.failure_code,
                "duplicate": False,
            }


def _retry_or_dead_letter(
    *,
    task: BoundRetryTask,
    envelope: TaskEnvelope,
    handler: str,
    attempt: int,
    error: TransientTaskError,
    session: Session,
    publisher: DeadLetterPublisher,
) -> TaskResult:
    max_retries = task.max_retries if task.max_retries is not None else 3
    if task.request.retries < max_retries:
        logger.warning(
            "Protected task scheduled for retry",
            extra={
                **_log_fields(task, envelope, handler, attempt),
                "failure_code": error.failure_code,
            },
        )
        record_task_consumer(task_type=handler, outcome="retry")
        raise task.retry(
            exc=error,
            countdown=_retry_delay(
                retry_index=task.request.retries,
                idempotency_key=envelope.task_context.idempotency_key,
            ),
        )
    terminal_error = PermanentTaskError(error.failure_code, str(error))
    _record_failure(
        session=session,
        envelope=envelope,
        handler=handler,
        attempt=attempt,
        error=terminal_error,
    )
    _publish_dead_letter(
        task=task,
        envelope=envelope,
        handler=handler,
        attempt=attempt,
        error=terminal_error,
        publisher=publisher,
    )
    record_task_consumer(task_type=handler, outcome="terminal")
    return {
        "status": "dead_lettered",
        "failure_code": error.failure_code,
        "duplicate": False,
    }


def _log_fields(
    task: BoundRetryTask,
    envelope: TaskEnvelope,
    handler: str,
    attempt: int,
) -> dict[str, object]:
    return {
        "task_id": task.request.id,
        "tenant_id": envelope.task_context.tenant_id,
        "idempotency_key": envelope.task_context.idempotency_key,
        "task_type": handler,
        "attempt": attempt,
        "correlation_id": envelope.task_context.correlation_id,
        "trace_id": envelope.task_context.trace_id,
    }


def _publish_dead_letter(
    *,
    task: BoundRetryTask,
    envelope: TaskEnvelope,
    handler: str,
    attempt: int,
    error: ClassifiedTaskError,
    publisher: DeadLetterPublisher,
) -> None:
    terminal = DeadLetterMessage(
        task_id=task.request.id,
        task_name=handler,
        tenant_id=envelope.task_context.tenant_id,
        idempotency_key=envelope.task_context.idempotency_key,
        correlation_id=envelope.task_context.correlation_id,
        trace_id=envelope.task_context.trace_id,
        attempt=attempt,
        failure_code=error.failure_code,
        failure_reason=pii_filter.filter_text(str(error)).redacted_text,
        envelope=envelope.model_dump(mode="json"),
    )
    _publish_dead_letter_message(
        publisher=publisher,
        message=terminal,
        log_fields=_log_fields(task, envelope, handler, attempt),
    )


def _publish_dead_letter_message(
    *,
    publisher: DeadLetterPublisher,
    message: DeadLetterMessage,
    log_fields: Mapping[str, object],
) -> None:
    """Publish terminal evidence or request redelivery if the DLQ is unavailable."""
    try:
        publisher.publish(message)
    except Exception as error:
        logger.exception("Dead-letter publication failed", extra=dict(log_fields))
        raise Reject("Dead-letter publication failed", requeue=True) from error
    record_task_consumer(task_type=message.task_name, outcome="dead_lettered")


def execute_db_task_once(
    *,
    session: Session,
    envelope: TaskEnvelope,
    handler: str,
    attempt: int,
    operation: DatabaseTaskHandler,
    lease_seconds: int = 300,
) -> TaskResult:
    """Apply a database-local task effect and success receipt in one transaction.

    A PostgreSQL transaction advisory lock serializes first delivery and duplicate
    delivery even before the unique receipt row exists. A process crash rolls back
    both the database effect and an uncommitted new receipt. Persisted stale
    ``PROCESSING`` receipts from compatible external flows can be reclaimed after
    their lease expires.
    """
    context = envelope.task_context
    now = utc_now()
    session.exec(
        select(
            func.pg_advisory_xact_lock(
                _advisory_lock_key(context.tenant_id, handler, context.idempotency_key)
            )
        )
    ).one()
    receipt = session.exec(
        select(TaskExecutionReceipt)
        .where(
            col(TaskExecutionReceipt.tenant_id) == context.tenant_id,
            col(TaskExecutionReceipt.handler) == handler,
            col(TaskExecutionReceipt.idempotency_key) == context.idempotency_key,
        )
        .with_for_update()
    ).one_or_none()

    if receipt is not None and receipt.status == TaskReceiptStatus.COMPLETED:
        result = dict(receipt.result or {"status": "success"})
        result["duplicate"] = True
        session.commit()
        return result
    if receipt is not None and receipt.status == TaskReceiptStatus.TERMINAL:
        failure_code = receipt.failure_code or "TERMINAL_RECEIPT"
        failure_reason = receipt.last_error or "Task already reached terminal failure"
        session.commit()
        raise PermanentTaskError(failure_code, failure_reason)
    if (
        receipt is not None
        and receipt.status == TaskReceiptStatus.PROCESSING
        and receipt.claim_expires_at is not None
        and receipt.claim_expires_at > now
    ):
        session.rollback()
        raise TaskReceiptInProgressError("Task receipt is owned by another active worker")

    if receipt is None:
        receipt = TaskExecutionReceipt(
            tenant_id=context.tenant_id,
            handler=handler,
            idempotency_key=context.idempotency_key,
        )

    receipt.status = TaskReceiptStatus.PROCESSING
    receipt.attempt_count = max(receipt.attempt_count, attempt)
    receipt.claim_token = uuid.uuid4()
    receipt.claim_expires_at = now + timedelta(seconds=lease_seconds)
    receipt.updated_at = now
    session.add(receipt)

    try:
        result = operation(session)
        completed_at = utc_now()
        receipt.status = TaskReceiptStatus.COMPLETED
        receipt.result = result
        receipt.failure_code = None
        receipt.last_error = None
        receipt.completed_at = completed_at
        receipt.updated_at = completed_at
        receipt.claim_token = None
        receipt.claim_expires_at = None
        session.add(receipt)
        session.commit()
        result["duplicate"] = False
        return result
    except ClassifiedTaskError as error:
        session.rollback()
        _record_failure(
            session=session,
            envelope=envelope,
            handler=handler,
            attempt=attempt,
            error=error,
        )
        raise
    except BaseException:
        session.rollback()
        raise


def execute_external_task_once(
    *,
    session: Session,
    envelope: TaskEnvelope,
    handler: str,
    attempt: int,
    operation: ExternalTaskHandler,
    lease_seconds: int = 300,
) -> TaskResult:
    """Execute one stable external projection with a recoverable receipt lease.

    Unlike ``execute_db_task_once``, this seam deliberately commits its receipt
    claim before calling the provider. A worker crash after the provider call
    leaves a lease that can later be reclaimed. Re-execution may occur, so the
    provider operation must use a stable idempotency identity.
    """
    context = envelope.task_context
    now = utc_now()
    session.exec(
        select(
            func.pg_advisory_xact_lock(
                _advisory_lock_key(context.tenant_id, handler, context.idempotency_key)
            )
        )
    ).one()
    receipt = session.exec(
        select(TaskExecutionReceipt)
        .where(
            col(TaskExecutionReceipt.tenant_id) == context.tenant_id,
            col(TaskExecutionReceipt.handler) == handler,
            col(TaskExecutionReceipt.idempotency_key) == context.idempotency_key,
        )
        .with_for_update()
    ).one_or_none()

    if receipt is not None and receipt.status == TaskReceiptStatus.COMPLETED:
        result = dict(receipt.result or {"status": "success"})
        result["duplicate"] = True
        session.commit()
        return result
    if receipt is not None and receipt.status == TaskReceiptStatus.TERMINAL:
        failure_code = receipt.failure_code or "TERMINAL_RECEIPT"
        failure_reason = receipt.last_error or "Task already reached terminal failure"
        session.commit()
        raise PermanentTaskError(failure_code, failure_reason)
    if (
        receipt is not None
        and receipt.status == TaskReceiptStatus.PROCESSING
        and receipt.claim_expires_at is not None
        and receipt.claim_expires_at > now
    ):
        session.rollback()
        raise TaskReceiptInProgressError("Task receipt is owned by another active worker")

    if receipt is None:
        receipt = TaskExecutionReceipt(
            tenant_id=context.tenant_id,
            handler=handler,
            idempotency_key=context.idempotency_key,
        )
    claim_token = uuid.uuid4()
    receipt.status = TaskReceiptStatus.PROCESSING
    receipt.attempt_count = max(receipt.attempt_count, attempt)
    receipt.claim_token = claim_token
    receipt.claim_expires_at = now + timedelta(seconds=lease_seconds)
    receipt.updated_at = now
    session.add(receipt)
    session.commit()

    try:
        result = operation()
    except ClassifiedTaskError as error:
        _record_failure(
            session=session,
            envelope=envelope,
            handler=handler,
            attempt=attempt,
            error=error,
        )
        raise
    except BaseException:
        session.rollback()
        raise

    session.exec(
        select(
            func.pg_advisory_xact_lock(
                _advisory_lock_key(context.tenant_id, handler, context.idempotency_key)
            )
        )
    ).one()
    receipt = session.exec(
        select(TaskExecutionReceipt)
        .where(
            col(TaskExecutionReceipt.tenant_id) == context.tenant_id,
            col(TaskExecutionReceipt.handler) == handler,
            col(TaskExecutionReceipt.idempotency_key) == context.idempotency_key,
        )
        .with_for_update()
    ).one()
    if receipt.status == TaskReceiptStatus.COMPLETED:
        completed_result = dict(receipt.result or result)
        completed_result["duplicate"] = True
        session.commit()
        return completed_result
    if receipt.claim_token != claim_token:
        session.rollback()
        raise TaskReceiptInProgressError("Task receipt lease changed before completion")

    completed_at = utc_now()
    receipt.status = TaskReceiptStatus.COMPLETED
    receipt.result = result
    receipt.failure_code = None
    receipt.last_error = None
    receipt.completed_at = completed_at
    receipt.updated_at = completed_at
    receipt.claim_token = None
    receipt.claim_expires_at = None
    session.add(receipt)
    session.commit()
    result["duplicate"] = False
    return result


def _record_failure(
    *,
    session: Session,
    envelope: TaskEnvelope,
    handler: str,
    attempt: int,
    error: ClassifiedTaskError,
) -> None:
    context = envelope.task_context
    session.exec(
        select(
            func.pg_advisory_xact_lock(
                _advisory_lock_key(context.tenant_id, handler, context.idempotency_key)
            )
        )
    ).one()
    receipt = session.exec(
        select(TaskExecutionReceipt)
        .where(
            col(TaskExecutionReceipt.tenant_id) == context.tenant_id,
            col(TaskExecutionReceipt.handler) == handler,
            col(TaskExecutionReceipt.idempotency_key) == context.idempotency_key,
        )
        .with_for_update()
    ).one_or_none()
    if receipt is None:
        receipt = TaskExecutionReceipt(
            tenant_id=context.tenant_id,
            handler=handler,
            idempotency_key=context.idempotency_key,
        )
    now = utc_now()
    receipt.status = TaskReceiptStatus.RETRYABLE if error.transient else TaskReceiptStatus.TERMINAL
    receipt.attempt_count = max(receipt.attempt_count, attempt)
    receipt.failure_code = error.failure_code
    receipt.last_error = pii_filter.filter_text(str(error)).redacted_text[:2000]
    receipt.updated_at = now
    receipt.claim_token = None
    receipt.claim_expires_at = None
    session.add(receipt)
    session.commit()
