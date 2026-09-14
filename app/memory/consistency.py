"""Transactional commands and asynchronous projection for structured memory."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from asgiref.sync import async_to_sync
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.tenancy import TenantIsolationError
from app.models.memory import InteractionSummary
from app.outbox.enqueue import enqueue_task
from app.task_runtime.context import TaskContext, build_task_context
from app.task_runtime.envelope import TaskEnvelope
from app.task_runtime.reliability import (
    PermanentTaskError,
    TaskResult,
    TransientTaskError,
    execute_external_task_once,
)

MEMORY_VECTOR_SYNC_TASK = "memory.sync_vector"
MEMORY_VECTOR_SYNC_EVENT = "memory.vector_sync.requested"
MEMORY_VECTOR_DELETE_EVENT = "memory.vector_delete.requested"


class MemoryVectorOperation(StrEnum):
    """Supported derived-index mutations."""

    UPSERT = "UPSERT"
    DELETE = "DELETE"


class VectorIndexUnavailableError(RuntimeError):
    """Provider adapter failure that is safe to retry with bounded policy."""


class MemoryVectorSyncPayload(BaseModel):
    """PII-free identity used to load authoritative memory in the worker."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    memory_id: int = Field(gt=0)
    version: int = Field(gt=0)
    operation: MemoryVectorOperation


class MemoryVectorDocument(BaseModel):
    """Authoritative snapshot passed in-process to the Qdrant adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant_id: str = Field(min_length=1, max_length=64)
    memory_id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    thread_id: str = Field(min_length=1, max_length=128)
    version: int = Field(gt=0)
    summary_text: str
    resolved_intent: str
    updated_at: str


class MemoryVectorIndex(Protocol):
    """Derived vector-index operations required by memory consistency."""

    async def upsert_summary(self, document: MemoryVectorDocument) -> None:
        """Replace the stable summary point with the supplied version."""
        ...

    async def delete_summary(self, *, tenant_id: str, memory_id: int) -> None:
        """Delete the stable summary point if it exists."""
        ...

    async def get_summary_version(self, *, tenant_id: str, memory_id: int) -> int | None:
        """Return the indexed version, or None when the point is absent."""
        ...


async def enqueue_summary_vector_sync(
    *,
    session: AsyncSession,
    record: InteractionSummary,
    task_context: TaskContext,
    operation: MemoryVectorOperation,
) -> None:
    """Persist vector intent in the caller-owned memory transaction."""
    if record.id is None:
        raise ValueError("Interaction summary must be flushed before vector enqueue")
    if task_context.user_id != record.user_id:
        raise ValueError("Task user does not own the interaction summary")
    if task_context.tenant_id != record.tenant_id:
        raise ValueError("Task tenant does not own the interaction summary")
    event_type = (
        MEMORY_VECTOR_SYNC_EVENT
        if operation == MemoryVectorOperation.UPSERT
        else MEMORY_VECTOR_DELETE_EVENT
    )
    await enqueue_task(
        session=session,
        task_name=MEMORY_VECTOR_SYNC_TASK,
        task_context=task_context,
        payload=MemoryVectorSyncPayload(
            memory_id=record.id,
            version=record.version,
            operation=operation,
        ),
        event_type=event_type,
        aggregate_type="interaction_summary",
        aggregate_id=str(record.id),
    )


def build_memory_vector_task_context(
    *,
    tenant_id: str,
    user_id: int,
    thread_id: str,
    correlation_id: str,
    trace_id: str | None,
    operation_id: str,
) -> TaskContext:
    """Build stable metadata for one versioned memory projection command."""
    return build_task_context(
        task_name=MEMORY_VECTOR_SYNC_TASK,
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        correlation_id=correlation_id,
        trace_id=trace_id,
        operation_id=operation_id,
    )


def _load_vector_action(
    *,
    session: Session,
    envelope: TaskEnvelope,
    payload: MemoryVectorSyncPayload,
) -> MemoryVectorDocument | MemoryVectorOperation | TaskResult:
    context = envelope.task_context
    record = session.exec(
        select(InteractionSummary).where(
            col(InteractionSummary.id) == payload.memory_id,
            col(InteractionSummary.user_id) == context.user_id,
        )
    ).one_or_none()
    if record is None:
        session.rollback()
        raise PermanentTaskError("MEMORY_NOT_FOUND", "Authoritative memory record was not found")
    if record.version > payload.version:
        session.rollback()
        return {
            "status": "stale_ignored",
            "memory_id": payload.memory_id,
            "event_version": payload.version,
            "authoritative_version": record.version,
        }
    if record.version < payload.version:
        session.rollback()
        raise TransientTaskError(
            "MEMORY_VERSION_NOT_VISIBLE",
            "Authoritative memory version is not visible yet",
        )
    if payload.operation == MemoryVectorOperation.DELETE:
        if not record.is_deleted:
            session.rollback()
            raise PermanentTaskError(
                "INVALID_MEMORY_DELETE", "Delete event targets an active memory record"
            )
        session.rollback()
        return MemoryVectorOperation.DELETE
    if record.is_deleted:
        session.rollback()
        return {
            "status": "stale_ignored",
            "memory_id": payload.memory_id,
            "event_version": payload.version,
            "authoritative_version": record.version,
        }

    document = MemoryVectorDocument(
        tenant_id=record.tenant_id,
        memory_id=payload.memory_id,
        user_id=record.user_id,
        thread_id=record.thread_id,
        version=record.version,
        summary_text=record.summary_text,
        resolved_intent=record.resolved_intent,
        updated_at=record.updated_at.isoformat(),
    )
    session.rollback()
    return document


def apply_memory_vector_sync(
    *,
    session: Session,
    envelope: TaskEnvelope,
    vector_index: MemoryVectorIndex,
) -> TaskResult:
    """Load the authoritative row, close the read transaction, then project."""
    payload = MemoryVectorSyncPayload.model_validate(envelope.payload)
    action = _load_vector_action(session=session, envelope=envelope, payload=payload)
    if isinstance(action, dict):
        return action
    if isinstance(action, MemoryVectorOperation) and action != MemoryVectorOperation.DELETE:
        raise PermanentTaskError("INVALID_MEMORY_OPERATION", "Unexpected projection operation")
    try:
        if isinstance(action, MemoryVectorOperation):
            async_to_sync(vector_index.delete_summary)(
                tenant_id=envelope.task_context.tenant_id,
                memory_id=payload.memory_id,
            )
            return {
                "status": "deleted",
                "memory_id": payload.memory_id,
                "version": payload.version,
            }
        async_to_sync(vector_index.upsert_summary)(action)
        return {
            "status": "indexed",
            "memory_id": payload.memory_id,
            "version": payload.version,
        }
    except TenantIsolationError as error:
        raise PermanentTaskError("VECTOR_TENANT_VIOLATION", type(error).__name__) from error
    except (
        ConnectionError,
        TimeoutError,
        OSError,
        OperationalError,
        VectorIndexUnavailableError,
    ) as error:
        raise TransientTaskError("VECTOR_INDEX_UNAVAILABLE", type(error).__name__) from error


def execute_memory_vector_sync_once(
    *,
    session: Session,
    envelope: TaskEnvelope,
    vector_index: MemoryVectorIndex,
    attempt: int,
) -> TaskResult:
    """Project one event through the shared crash-recoverable receipt store."""
    return execute_external_task_once(
        session=session,
        envelope=envelope,
        handler=MEMORY_VECTOR_SYNC_TASK,
        attempt=attempt,
        operation=lambda: apply_memory_vector_sync(
            session=session,
            envelope=envelope,
            vector_index=vector_index,
        ),
    )


async def reconcile_summary_vectors(
    *,
    session: AsyncSession,
    task_context: TaskContext,
    vector_index: MemoryVectorIndex,
) -> int:
    """Detect tenant-local projection drift and enqueue versioned repair intent.

    The caller owns the transaction. Each repair gets an identity derived from
    the reconciliation correlation so repeated scans in one run deduplicate,
    while a later run can repair an event that previously reached a terminal
    broker outcome.
    """
    records = list(
        (
            await session.exec(
                select(InteractionSummary).where(
                    col(InteractionSummary.user_id) == task_context.user_id
                )
            )
        ).all()
    )
    enqueued = 0
    for record in records:
        if record.id is None:
            continue
        indexed_version = await vector_index.get_summary_version(
            tenant_id=record.tenant_id,
            memory_id=record.id,
        )
        is_drifted = (
            indexed_version is not None if record.is_deleted else indexed_version != record.version
        )
        if not is_drifted:
            continue
        operation = (
            MemoryVectorOperation.DELETE if record.is_deleted else MemoryVectorOperation.UPSERT
        )
        repair_context = build_memory_vector_task_context(
            tenant_id=task_context.tenant_id,
            user_id=task_context.user_id,
            thread_id=record.thread_id,
            correlation_id=task_context.correlation_id,
            trace_id=task_context.trace_id,
            operation_id=(
                f"summary:{record.id}:v{record.version}:{operation.value.lower()}:"
                f"reconcile:{task_context.correlation_id}"
            ),
        )
        await enqueue_summary_vector_sync(
            session=session,
            record=record,
            task_context=repair_context,
            operation=operation,
        )
        enqueued += 1
    return enqueued
