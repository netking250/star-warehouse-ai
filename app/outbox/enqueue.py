"""Caller-owned transactional enqueue interface."""

from __future__ import annotations

import json

from pydantic import BaseModel, JsonValue
from sqlmodel.ext.asyncio.session import AsyncSession

from app.context.pii_filter import pii_filter
from app.core.tenancy import TenantIsolationError, get_current_tenant_id
from app.models.outbox import OutboxEvent
from app.task_runtime.context import TaskContext
from app.task_runtime.envelope import TaskEnvelope

_FORBIDDEN_RAW_PAYLOAD_KEYS = frozenset(
    {
        "email",
        "original_question",
        "phone",
        "query",
        "question",
        "raw_question",
        "recipient_email",
    }
)


def _contains_forbidden_key(value: JsonValue) -> bool:
    if isinstance(value, dict):
        return any(
            key.lower() in _FORBIDDEN_RAW_PAYLOAD_KEYS or _contains_forbidden_key(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_forbidden_key(item) for item in value)
    return False


def _validate_sanitized_payload(payload: dict[str, JsonValue]) -> None:
    if _contains_forbidden_key(payload):
        raise ValueError("Outbox payload contains a forbidden raw request or recipient field")
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if pii_filter.filter_text(serialized).has_pii:
        raise ValueError("Outbox payload contains unredacted PII")


async def enqueue_task(
    *,
    session: AsyncSession,
    task_name: str,
    task_context: TaskContext,
    payload: BaseModel | dict[str, JsonValue],
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
) -> OutboxEvent:
    """Add one task envelope to the caller's current transaction.

    The function deliberately never commits. A flush surfaces persistence and
    idempotency conflicts while leaving commit or rollback ownership with the
    business use case.
    """
    serialized_payload = (
        payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
    )
    active_tenant_id = get_current_tenant_id()
    if active_tenant_id != task_context.tenant_id:
        raise TenantIsolationError(
            f"Cannot enqueue tenant {task_context.tenant_id!r} while scoped to {active_tenant_id!r}"
        )
    _validate_sanitized_payload(serialized_payload)
    task_envelope = TaskEnvelope(task_context=task_context, payload=serialized_payload)
    event = OutboxEvent(
        tenant_id=task_context.tenant_id,
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        task_name=task_name,
        envelope=task_envelope.model_dump(mode="json"),
        idempotency_key=task_context.idempotency_key,
    )
    session.add(event)
    await session.flush()
    return event
