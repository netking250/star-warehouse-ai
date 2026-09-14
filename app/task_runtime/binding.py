"""Worker-side task context binding and cleanup lifecycle."""

from __future__ import annotations

import contextvars
import logging
from collections.abc import Iterator
from contextlib import contextmanager

from opentelemetry import context as otel_context
from opentelemetry import propagate, trace

from app.core.logging import correlation_id
from app.core.tenancy import (
    TenantContext,
    reset_current_tenant_id,
    set_current_tenant_context,
    set_current_tenant_id,
)
from app.task_runtime.context import SystemTaskContext, TaskContext

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

ExecutionTaskContext = TaskContext | SystemTaskContext

_current_task_context: contextvars.ContextVar[ExecutionTaskContext | None] = contextvars.ContextVar(
    "task_context", default=None
)


class TaskContextNotBoundError(RuntimeError):
    """Raised when tenant task metadata is accessed outside worker binding."""


def get_current_task_context() -> ExecutionTaskContext:
    """Return the validated context bound to the current worker execution."""
    current = _current_task_context.get()
    if current is None:
        raise TaskContextNotBoundError("No tenant task context is bound")
    return current


@contextmanager
def bind_task_context(
    task_context: TaskContext,
    *,
    tenant_context: TenantContext | None = None,
) -> Iterator[None]:
    """Bind tenant, correlation, trace, and task context, then always restore them."""
    tenant_token = (
        set_current_tenant_id(task_context.tenant_id)
        if tenant_context is None
        else set_current_tenant_context(tenant_context)
    )
    correlation_token = correlation_id.set(task_context.correlation_id)
    task_token = _current_task_context.set(task_context)
    extracted_context = propagate.extract(task_context.trace_context)
    otel_token = otel_context.attach(extracted_context)
    try:
        yield
    finally:
        otel_context.detach(otel_token)
        _current_task_context.reset(task_token)
        correlation_id.reset(correlation_token)
        reset_current_tenant_id(tenant_token)


@contextmanager
def bind_system_task_context(task_context: SystemTaskContext) -> Iterator[None]:
    """Bind an explicitly global task without inventing a tenant identity."""
    correlation_token = correlation_id.set(task_context.correlation_id)
    task_token = _current_task_context.set(task_context)
    extracted_context = propagate.extract(task_context.trace_context)
    otel_token = otel_context.attach(extracted_context)
    try:
        yield
    finally:
        otel_context.detach(otel_token)
        _current_task_context.reset(task_token)
        correlation_id.reset(correlation_token)


@contextmanager
def task_execution_scope(
    task_context: ExecutionTaskContext,
    *,
    task_name: str,
    task_id: str | None,
) -> Iterator[None]:
    """Validate and bind a worker context while emitting one correlated child span."""
    effective_task_id = task_id or task_context.idempotency_key
    if isinstance(task_context, TaskContext):
        from app.core.database import sync_session_maker
        from app.core.tenant_resolver import resolve_tenant_sync

        with sync_session_maker() as session:
            tenant_context = resolve_tenant_sync(session, task_context.tenant_id)
        binding = bind_task_context(task_context, tenant_context=tenant_context)
    else:
        binding = bind_system_task_context(task_context)
    with binding, tracer.start_as_current_span(task_name) as span:
        span.set_attribute("task.id", effective_task_id)
        span.set_attribute("task.idempotency_key", task_context.idempotency_key)
        span.set_attribute("task.scope", task_context.scope)
        span.set_attribute("correlation.id", task_context.correlation_id)
        if isinstance(task_context, TaskContext):
            span.set_attribute("tenant.id", task_context.tenant_id)
        if isinstance(task_context, TaskContext) and task_context.thread_id is not None:
            span.set_attribute("conversation.thread_id", task_context.thread_id)
        logger.info(
            "Task execution context bound",
            extra={
                "task_id": effective_task_id,
                "idempotency_key": task_context.idempotency_key,
                "tenant_id": task_context.tenant_id,
            },
        )
        yield
