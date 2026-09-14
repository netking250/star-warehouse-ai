"""Typed metadata propagated across asynchronous task boundaries."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

from opentelemetry import propagate, trace
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.tenancy import validate_tenant_id

_TRACE_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")


def _stable_idempotency_key(
    *,
    task_name: str,
    scope: str,
    tenant_id: str | None,
    user_id: int | None,
    correlation_id: str,
    thread_id: str | None,
    operation_id: str | None,
) -> str:
    identity = json.dumps(
        {
            "correlation_id": correlation_id,
            "scope": scope,
            "task_name": task_name,
            "tenant_id": tenant_id,
            "thread_id": thread_id,
            "user_id": user_id,
            "operation_id": operation_id,
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return f"{task_name}:v1:{digest}"


def _current_trace() -> tuple[str | None, dict[str, str]]:
    carrier: dict[str, str] = {}
    propagate.inject(carrier)
    span_context = trace.get_current_span().get_span_context()
    trace_id = format(span_context.trace_id, "032x") if span_context.is_valid else None
    return trace_id, carrier


class TaskContext(BaseModel):
    """Trusted metadata required by a tenant-scoped background task."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scope: Literal["tenant"] = "tenant"
    tenant_id: str = Field(min_length=1, max_length=64)
    user_id: int = Field(gt=0)
    correlation_id: str = Field(min_length=1, max_length=128)
    trace_id: str | None
    idempotency_key: str = Field(min_length=1, max_length=192)
    thread_id: str | None = Field(default=None, max_length=128)
    trace_context: dict[str, str] = Field(default_factory=dict)

    @field_validator("tenant_id")
    @classmethod
    def _validate_tenant(cls, value: str) -> str:
        return validate_tenant_id(value)

    @field_validator("correlation_id")
    @classmethod
    def _validate_correlation(cls, value: str) -> str:
        if value == "-":
            raise ValueError("correlation_id must be explicitly propagated")
        return value

    @field_validator("trace_id")
    @classmethod
    def _validate_trace_id(cls, value: str | None) -> str | None:
        if value is not None and not _TRACE_ID_PATTERN.fullmatch(value.lower()):
            raise ValueError("trace_id must be a 32-character lowercase hexadecimal value")
        return value.lower() if value is not None else None

    @model_validator(mode="after")
    def _validate_trace_carrier(self) -> TaskContext:
        traceparent = self.trace_context.get("traceparent")
        if traceparent and self.trace_id is not None:
            parts = traceparent.split("-")
            if len(parts) != 4 or parts[1].lower() != self.trace_id:
                raise ValueError("trace_context does not match trace_id")
        return self


class SystemTaskContext(BaseModel):
    """Explicit metadata for a global task that has no tenant or user identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scope: Literal["system"] = "system"
    tenant_id: None = None
    user_id: None = None
    correlation_id: str = Field(min_length=1, max_length=128)
    trace_id: str | None
    idempotency_key: str = Field(min_length=1, max_length=192)
    trace_context: dict[str, str] = Field(default_factory=dict)


def build_task_context(
    *,
    task_name: str,
    tenant_id: str,
    user_id: int,
    correlation_id: str,
    thread_id: str | None = None,
    trace_id: str | None = None,
    trace_context: dict[str, str] | None = None,
    operation_id: str | None = None,
) -> TaskContext:
    """Build validated tenant task metadata with a deterministic identity."""
    current_trace_id, current_carrier = _current_trace()
    effective_trace_id = trace_id if trace_id is not None else current_trace_id
    effective_carrier = dict(trace_context) if trace_context is not None else current_carrier
    return TaskContext(
        tenant_id=tenant_id,
        user_id=user_id,
        correlation_id=correlation_id,
        trace_id=effective_trace_id,
        idempotency_key=_stable_idempotency_key(
            task_name=task_name,
            scope="tenant",
            tenant_id=tenant_id,
            user_id=user_id,
            correlation_id=correlation_id,
            thread_id=thread_id,
            operation_id=operation_id,
        ),
        thread_id=thread_id,
        trace_context=effective_carrier,
    )


def build_system_task_context(*, task_name: str, schedule_identity: str) -> SystemTaskContext:
    """Build explicit global-task metadata without inventing a default tenant."""
    trace_id, carrier = _current_trace()
    correlation_id = f"system:{task_name}:{schedule_identity}"
    return SystemTaskContext(
        correlation_id=correlation_id,
        trace_id=trace_id,
        idempotency_key=_stable_idempotency_key(
            task_name=task_name,
            scope="system",
            tenant_id=None,
            user_id=None,
            correlation_id=correlation_id,
            thread_id=None,
            operation_id=schedule_identity,
        ),
        trace_context=carrier,
    )
