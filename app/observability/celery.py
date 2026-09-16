"""Celery lifecycle instrumentation with bounded labels and no task-payload inspection."""

from __future__ import annotations

import contextvars
import logging
import time
from collections.abc import Mapping

from celery.signals import (
    beat_init,
    setup_logging,
    task_failure,
    task_postrun,
    task_prerun,
    task_received,
    task_rejected,
    task_retry,
    task_revoked,
)

from app.core.config import settings
from app.core.structured_logging import configure_logging
from app.observability.metrics import (
    record_celery_task_duration,
    record_celery_task_event,
    set_celery_task_in_flight,
)

logger = logging.getLogger(__name__)

_TaskStart = tuple[str, float]
_task_start: contextvars.ContextVar[_TaskStart | None] = contextvars.ContextVar(
    "celery_observability_task_start", default=None
)
_installed = False


@setup_logging.connect(weak=False)
def on_celery_setup_logging(**_: object) -> None:
    """Configure worker and beat logs as safe JSON before Celery starts emitting events."""
    configure_logging(log_format=settings.LOG_FORMAT)


def _task_name(sender: object | None, request: object | None = None) -> str:
    """Extract a registered task name without reading arguments or payloads."""
    for candidate in (getattr(sender, "name", None), getattr(request, "name", None)):
        if isinstance(candidate, str) and candidate:
            return candidate
    return "unknown"


def _task_id(task_id: object | None, request: object | None = None) -> str | None:
    """Extract an ID for diagnostic logs only."""
    candidate = task_id if isinstance(task_id, str) else getattr(request, "id", None)
    return candidate if isinstance(candidate, str) else None


def _queue(request: object | None) -> str:
    """Extract the broker routing key without inspecting the message body."""
    delivery_info = getattr(request, "delivery_info", None)
    if not isinstance(delivery_info, Mapping):
        return "unknown"
    queue = delivery_info.get("routing_key", delivery_info.get("queue"))
    return queue if isinstance(queue, str) else "unknown"


def _signal_request(kwargs: Mapping[str, object]) -> object | None:
    """Return the Celery request object supplied by a lifecycle signal."""
    request = kwargs.get("request")
    if request is not None:
        return request
    task = kwargs.get("task")
    return getattr(task, "request", None)


def _record_event(*, task_type: str, queue: str, outcome: str) -> None:
    """Record an event defensively so instrumentation cannot affect task execution."""
    try:
        record_celery_task_event(task_type=task_type, queue=queue, outcome=outcome)
    except Exception as telemetry_error:
        logger.debug("Celery metric recording unavailable: %s", type(telemetry_error).__name__)


def _record_duration(*, task_type: str, outcome: str, duration_seconds: float) -> None:
    """Record a task duration defensively."""
    try:
        record_celery_task_duration(
            task_type=task_type,
            outcome=outcome,
            duration_seconds=duration_seconds,
        )
    except Exception as telemetry_error:
        logger.debug("Celery duration metric unavailable: %s", type(telemetry_error).__name__)


@task_received.connect(weak=False)
def on_task_received(
    *, sender: object | None = None, request: object | None = None, **_: object
) -> None:
    """Record broker acceptance for a task without inspecting its arguments."""
    task_type = _task_name(sender, request)
    queue = _queue(request)
    _record_event(task_type=task_type, queue=queue, outcome="accepted")


@task_prerun.connect(weak=False)
def on_task_prerun(
    *, sender: object | None = None, task_id: str | None = None, **kwargs: object
) -> None:
    """Record task start and establish a process-local duration marker."""
    task_type = _task_name(sender)
    queue = _queue(_signal_request(kwargs))
    _task_start.set((task_id or "unknown", time.perf_counter()))
    try:
        set_celery_task_in_flight(task_type=task_type, delta=1)
    except Exception as telemetry_error:
        logger.debug("Celery in-flight metric unavailable: %s", type(telemetry_error).__name__)
    _record_event(task_type=task_type, queue=queue, outcome="started")
    logger.info(
        "Celery task started",
        extra={
            "event": "celery_task_started",
            "task_type": task_type,
            "queue": queue,
            "task_id": task_id,
        },
    )


@task_retry.connect(weak=False)
def on_task_retry(
    *, sender: object | None = None, request: object | None = None, **_: object
) -> None:
    """Record a retry decision without logging the exception or task payload."""
    _record_event(task_type=_task_name(sender, request), queue=_queue(request), outcome="retried")


@task_failure.connect(weak=False)
def on_task_failure(
    *, sender: object | None = None, task_id: str | None = None, **kwargs: object
) -> None:
    """Record a failed task attempt without serializing exception details."""
    request = _signal_request(kwargs)
    task_type = _task_name(sender, request)
    _record_event(task_type=task_type, queue=_queue(request), outcome="failed")
    logger.error(
        "Celery task failed",
        extra={
            "event": "celery_task_failed",
            "task_type": task_type,
            "task_id": _task_id(task_id, request),
            "error_category": "task_failure",
        },
    )


@task_rejected.connect(weak=False)
def on_task_rejected(
    *, sender: object | None = None, request: object | None = None, **_: object
) -> None:
    """Record broker rejection as a bounded lifecycle event."""
    _record_event(task_type=_task_name(sender, request), queue=_queue(request), outcome="rejected")


@task_revoked.connect(weak=False)
def on_task_revoked(
    *, sender: object | None = None, request: object | None = None, **_: object
) -> None:
    """Record task revocation as a cancellation outcome."""
    _record_event(task_type=_task_name(sender, request), queue=_queue(request), outcome="cancelled")


@task_postrun.connect(weak=False)
def on_task_postrun(
    *,
    sender: object | None = None,
    task_id: str | None = None,
    state: str | None = None,
    **kwargs: object,
) -> None:
    """Record terminal task state and release the local duration marker."""
    request = _signal_request(kwargs)
    task_type = _task_name(sender, request)
    queue = _queue(request)
    normalized_state = (state or "FAILURE").upper()
    outcome = {
        "SUCCESS": "succeeded",
        "RETRY": "retried",
        "REVOKED": "cancelled",
    }.get(normalized_state, "failed")
    started = _task_start.get()
    _task_start.set(None)
    if started is not None and (
        task_id is None or started[0] == task_id or started[0] == "unknown"
    ):
        _record_duration(
            task_type=task_type,
            outcome=outcome,
            duration_seconds=time.perf_counter() - started[1],
        )
        try:
            set_celery_task_in_flight(task_type=task_type, delta=-1)
        except Exception as telemetry_error:
            logger.debug("Celery in-flight metric unavailable: %s", type(telemetry_error).__name__)
    # A retry signal already records the retry decision. The post-run metric still observes its
    # duration, but avoids double-counting the lifecycle event.
    if outcome != "retried":
        _record_event(task_type=task_type, queue=queue, outcome=outcome)


@beat_init.connect(weak=False)
def on_beat_init(*, sender: object | None = None, **_: object) -> None:
    """Emit a safe scheduler-start event for the independent Beat boundary."""
    logger.info(
        "Celery scheduler started",
        extra={"event": "celery_scheduler_started", "service": "scheduler"},
    )


def setup_celery_observability() -> None:
    """Install lifecycle signal handlers once in the current Celery process."""
    global _installed
    if _installed:
        return
    # Handlers are connected by decorators at import time. This function is an explicit bootstrap
    # seam and idempotence guard so Celery application construction remains easy to audit.
    _installed = True
