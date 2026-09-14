"""Tests for trusted request-to-task execution context."""

import json
import uuid

import pytest
from opentelemetry import trace
from pydantic import ValidationError

from app.core.database import sync_session_maker
from app.core.logging import get_correlation_id
from app.core.tenancy import (
    TenantStatus,
    TenantSuspendedError,
    get_current_tenant_context,
    get_current_tenant_id,
    tenant_scope,
)
from app.models.tenant import Tenant
from app.task_runtime.binding import (
    TaskContextNotBoundError,
    bind_task_context,
    get_current_task_context,
    task_execution_scope,
)
from app.task_runtime.context import TaskContext, build_task_context
from app.task_runtime.envelope import TaskEnvelope
from app.tasks.observability_tasks import log_chat_observability


def _context(tenant_id: str, correlation_id: str) -> TaskContext:
    return build_task_context(
        task_name="tests.context",
        tenant_id=tenant_id,
        user_id=42,
        correlation_id=correlation_id,
        trace_id="1" * 32,
        thread_id="thread-42",
        trace_context={"traceparent": f"00-{'1' * 32}-{'2' * 16}-01"},
    )


def test_task_envelope_round_trips_through_celery_json() -> None:
    """The envelope must remain valid after JSON serialization."""
    envelope = TaskEnvelope(
        task_context=_context("tenant-blue", "correlation-blue"),
        payload={"sanitized_text": "phone [PHONE_REDACTED]"},
    )

    encoded = json.dumps(envelope.to_message())
    restored = TaskEnvelope.from_message(json.loads(encoded))

    assert restored.schema_version == 1
    assert restored.task_context.tenant_id == "tenant-blue"
    assert restored.payload == {"sanitized_text": "phone [PHONE_REDACTED]"}


def test_task_context_missing_tenant_fails_closed() -> None:
    """Tenant tasks must never infer a missing tenant."""
    message = {
        "tenant_id": None,
        "user_id": 42,
        "correlation_id": "correlation-missing",
        "trace_id": None,
        "idempotency_key": "task:v1:missing",
    }

    with pytest.raises(ValidationError):
        TaskContext.model_validate(message)


def test_tenant_worker_rejects_envelope_with_missing_tenant() -> None:
    """The real worker entry point must reject context before executing its handler."""
    malformed_envelope = {
        "schema_version": 1,
        "task_context": {
            "scope": "tenant",
            "user_id": 42,
            "correlation_id": "correlation-missing",
            "trace_id": None,
            "idempotency_key": "task:v1:missing",
            "trace_context": {},
        },
        "payload": {},
    }

    with pytest.raises(ValidationError):
        log_chat_observability.run(envelope=malformed_envelope)


def test_task_binding_sets_and_cleans_tenant_and_correlation() -> None:
    """Worker binding must restore the prior context after execution."""
    with tenant_scope("outer-tenant"):
        previous_correlation = get_correlation_id()
        with bind_task_context(_context("tenant-blue", "correlation-blue")):
            assert get_current_tenant_id() == "tenant-blue"
            assert get_correlation_id() == "correlation-blue"
            assert get_current_task_context().tenant_id == "tenant-blue"
            assert trace.get_current_span().get_span_context().trace_id == int("1" * 32, 16)

        assert get_current_tenant_id() == "outer-tenant"
        assert get_correlation_id() == previous_correlation

    with pytest.raises(TaskContextNotBoundError):
        get_current_task_context()


def test_sequential_task_bindings_do_not_leak_tenants() -> None:
    """A reused worker execution context must isolate consecutive tenants."""
    observed: list[tuple[str, str]] = []

    for tenant_id, correlation_id in (
        ("tenant-a", "correlation-a"),
        ("tenant-b", "correlation-b"),
    ):
        with bind_task_context(_context(tenant_id, correlation_id)):
            observed.append((get_current_tenant_id(), get_correlation_id()))

    assert observed == [
        ("tenant-a", "correlation-a"),
        ("tenant-b", "correlation-b"),
    ]
    with pytest.raises(TaskContextNotBoundError):
        get_current_task_context()


def test_idempotency_identity_is_stable_and_context_metadata_is_preserved() -> None:
    """Equivalent logical dispatches must produce the same non-PII identity."""
    first = _context("tenant-blue", "correlation-blue")
    second = _context("tenant-blue", "correlation-blue")

    assert first.idempotency_key == second.idempotency_key
    assert "tenant-blue" not in first.idempotency_key
    assert first.trace_id == "1" * 32
    assert first.correlation_id == "correlation-blue"
    assert first.thread_id == "thread-42"
    assert first.trace_context["traceparent"].startswith("00-")


def _persist_tenant(tenant_id: str, status: TenantStatus) -> None:
    with sync_session_maker() as session:
        session.add(
            Tenant(
                id=tenant_id,
                slug=tenant_id,
                display_name="Task Tenant",
                status=status,
            )
        )
        session.commit()


def _delete_tenant(tenant_id: str) -> None:
    with sync_session_maker() as session:
        tenant = session.get(Tenant, tenant_id)
        if tenant is not None:
            session.delete(tenant)
            session.commit()


def test_task_execution_scope_revalidates_and_binds_active_tenant() -> None:
    tenant_id = f"tenant-task-active-{uuid.uuid4().hex[:8]}"
    _persist_tenant(tenant_id, TenantStatus.ACTIVE)
    try:
        with task_execution_scope(
            _context(tenant_id, "correlation-task-active"),
            task_name="celery.tests.context",
            task_id="task-active",
        ):
            assert get_current_tenant_context().tenant_id == tenant_id
            assert get_current_tenant_context().status == TenantStatus.ACTIVE
    finally:
        _delete_tenant(tenant_id)


def test_task_execution_scope_blocks_suspended_tenant_before_handler() -> None:
    tenant_id = f"tenant-task-suspended-{uuid.uuid4().hex[:8]}"
    _persist_tenant(tenant_id, TenantStatus.SUSPENDED)
    handler_entered = False
    try:
        with (
            pytest.raises(TenantSuspendedError),
            task_execution_scope(
                _context(tenant_id, "correlation-task-suspended"),
                task_name="celery.tests.context",
                task_id="task-suspended",
            ),
        ):
            handler_entered = True
    finally:
        _delete_tenant(tenant_id)

    assert handler_entered is False
