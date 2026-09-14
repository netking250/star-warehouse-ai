"""Transactional memory projection consistency tests."""

from __future__ import annotations

import uuid
from collections.abc import Mapping

import pytest
from pydantic import JsonValue
from sqlmodel import Session, select

from app.core.database import async_session_maker, sync_session_maker
from app.core.tenancy import TenantStatus, tenant_scope
from app.memory.consistency import (
    MemoryVectorDocument,
    MemoryVectorOperation,
    MemoryVectorSyncPayload,
    execute_memory_vector_sync_once,
    reconcile_summary_vectors,
)
from app.memory.structured_manager import StructuredMemoryManager
from app.models.memory import InteractionSummary
from app.models.outbox import OutboxEvent
from app.models.task_receipt import TaskExecutionReceipt, TaskReceiptStatus
from app.models.tenant import Tenant
from app.models.user import User
from app.task_runtime.context import build_task_context
from app.task_runtime.dead_letter import DeadLetterMessage
from app.task_runtime.envelope import TaskEnvelope
from app.task_runtime.reliability import PermanentTaskError, TransientTaskError
from app.tasks.memory_tasks import sync_memory_vector


class RecordingVectorIndex:
    """In-memory substitute for the Qdrant system boundary."""

    def __init__(self, *, failures: int = 0) -> None:
        self.failures = failures
        self.upserts: list[MemoryVectorDocument] = []
        self.deletes: list[tuple[str, int]] = []
        self.versions: dict[tuple[str, int], int] = {}

    async def upsert_summary(self, document: MemoryVectorDocument) -> None:
        if self.failures:
            self.failures -= 1
            raise ConnectionError("Qdrant unavailable")
        self.upserts.append(document)
        self.versions[(document.tenant_id, document.memory_id)] = document.version

    async def delete_summary(self, *, tenant_id: str, memory_id: int) -> None:
        if self.failures:
            self.failures -= 1
            raise ConnectionError("Qdrant unavailable")
        self.deletes.append((tenant_id, memory_id))
        self.versions.pop((tenant_id, memory_id), None)

    async def get_summary_version(self, *, tenant_id: str, memory_id: int) -> int | None:
        return self.versions.get((tenant_id, memory_id))


class NoopDeadLetterPublisher:
    """Fail the test if a successful projection tries to dead-letter."""

    def publish(self, message: DeadLetterMessage) -> str:
        raise AssertionError(f"unexpected dead letter: {message.failure_code}")


async def _create_user(session, tenant_id: str) -> User:
    if await session.get(Tenant, tenant_id) is None:
        session.add(
            Tenant(
                id=tenant_id,
                slug=tenant_id,
                display_name="Memory Test Tenant",
                status=TenantStatus.ACTIVE,
            )
        )
        await session.flush()
    user = User(
        tenant_id=tenant_id,
        username=f"memory-{uuid.uuid4().hex}",
        email=f"memory-{uuid.uuid4().hex}@example.com",
        full_name="Memory Test",
        password_hash=User.hash_password("password"),
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


def _context(*, tenant_id: str, user_id: int, thread_id: str, operation_id: str):
    return build_task_context(
        task_name="memory.sync_vector",
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        correlation_id=f"corr-{uuid.uuid4().hex}",
        operation_id=operation_id,
    )


async def _committed_summary(*, tenant_id: str, thread_id: str) -> tuple[int, int, TaskEnvelope]:
    manager = StructuredMemoryManager()
    with tenant_scope(tenant_id):
        async with async_session_maker() as session:
            user = await _create_user(session, tenant_id)
            assert user.id is not None
            context = _context(
                tenant_id=tenant_id,
                user_id=user.id,
                thread_id=thread_id,
                operation_id=f"summary:{thread_id}:v1:upsert",
            )
            record = await manager.save_interaction_summary(
                session=session,
                task_context=context,
                user_id=user.id,
                thread_id=thread_id,
                summary="Authoritative summary",
                resolved_intent="LOGISTICS",
            )
            assert record.id is not None
            event = (
                await session.exec(
                    select(OutboxEvent).where(OutboxEvent.aggregate_id == str(record.id))
                )
            ).one()
            envelope = TaskEnvelope.model_validate(event.envelope)
            await session.commit()
            return user.id, record.id, envelope


def _stored_summary(
    *, session: Session, tenant_id: str, thread_id: str
) -> tuple[int, int, TaskEnvelope]:
    if session.get(Tenant, tenant_id) is None:
        session.add(
            Tenant(
                id=tenant_id,
                slug=tenant_id,
                display_name="Memory Sync Test Tenant",
                status=TenantStatus.ACTIVE,
            )
        )
        session.flush()
    user = User(
        tenant_id=tenant_id,
        username=f"memory-sync-{uuid.uuid4().hex}",
        email=f"memory-sync-{uuid.uuid4().hex}@example.com",
        full_name="Memory Sync Test",
        password_hash=User.hash_password("password"),
    )
    session.add(user)
    session.flush()
    assert user.id is not None
    record = InteractionSummary(
        tenant_id=tenant_id,
        user_id=user.id,
        thread_id=thread_id,
        summary_text="Authoritative summary",
        resolved_intent="LOGISTICS",
    )
    session.add(record)
    session.commit()
    assert record.id is not None
    context = _context(
        tenant_id=tenant_id,
        user_id=user.id,
        thread_id=thread_id,
        operation_id=f"summary:{thread_id}:v1:upsert",
    )
    envelope = TaskEnvelope(
        task_context=context,
        payload=MemoryVectorSyncPayload(
            memory_id=record.id,
            version=1,
            operation=MemoryVectorOperation.UPSERT,
        ).model_dump(mode="json"),
    )
    return user.id, record.id, envelope


@pytest.mark.asyncio
async def test_memory_command_commit_survives_a_new_session() -> None:
    tenant_id = f"tenant-memory-persist-{uuid.uuid4().hex[:8]}"
    thread_id = f"thread-{uuid.uuid4().hex}"
    user_id, memory_id, _ = await _committed_summary(tenant_id=tenant_id, thread_id=thread_id)

    with tenant_scope(tenant_id):
        async with async_session_maker() as second_session:
            record = (
                await second_session.exec(
                    select(InteractionSummary).where(InteractionSummary.id == memory_id)
                )
            ).one()
            event = (
                await second_session.exec(
                    select(OutboxEvent).where(OutboxEvent.aggregate_id == str(memory_id))
                )
            ).one()

    assert record.user_id == user_id
    assert record.version == 1
    assert event.task_name == "memory.sync_vector"
    assert event.tenant_id == tenant_id
    assert "Authoritative summary" not in str(event.envelope)


@pytest.mark.asyncio
async def test_memory_command_rollback_removes_summary_and_outbox() -> None:
    tenant_id = f"tenant-memory-rollback-{uuid.uuid4().hex[:8]}"
    thread_id = f"thread-{uuid.uuid4().hex}"
    manager = StructuredMemoryManager()

    with tenant_scope(tenant_id):
        async with async_session_maker() as session:
            user = await _create_user(session, tenant_id)
            assert user.id is not None
            await session.commit()
            context = _context(
                tenant_id=tenant_id,
                user_id=user.id,
                thread_id=thread_id,
                operation_id=f"summary:{thread_id}:v1:upsert",
            )
            record = await manager.save_interaction_summary(
                session=session,
                task_context=context,
                user_id=user.id,
                thread_id=thread_id,
                summary="Must roll back",
            )
            assert record.id is not None
            memory_id = record.id
            await session.rollback()

        async with async_session_maker() as verifier:
            summary = (
                await verifier.exec(
                    select(InteractionSummary).where(InteractionSummary.id == memory_id)
                )
            ).one_or_none()
            event = (
                await verifier.exec(
                    select(OutboxEvent).where(OutboxEvent.aggregate_id == str(memory_id))
                )
            ).one_or_none()

    assert summary is None
    assert event is None


@pytest.mark.asyncio
async def test_memory_delete_commits_tombstone_and_vector_delete_intent() -> None:
    tenant_id = f"tenant-memory-delete-{uuid.uuid4().hex[:8]}"
    thread_id = f"thread-{uuid.uuid4().hex}"
    user_id, memory_id, _ = await _committed_summary(tenant_id=tenant_id, thread_id=thread_id)
    manager = StructuredMemoryManager()

    with tenant_scope(tenant_id):
        async with async_session_maker() as session:
            context = _context(
                tenant_id=tenant_id,
                user_id=user_id,
                thread_id=thread_id,
                operation_id=f"summary:{memory_id}:v2:delete",
            )
            await manager.delete_interaction_summary(
                session=session,
                task_context=context,
                memory_id=memory_id,
                user_id=user_id,
            )
            await session.commit()

        async with async_session_maker() as verifier:
            record = (
                await verifier.exec(
                    select(InteractionSummary).where(InteractionSummary.id == memory_id)
                )
            ).one()
            delete_event = (
                await verifier.exec(
                    select(OutboxEvent).where(
                        OutboxEvent.aggregate_id == str(memory_id),
                        OutboxEvent.event_type == "memory.vector_delete.requested",
                    )
                )
            ).one()

    payload = TaskEnvelope.model_validate(delete_event.envelope).payload
    assert record.is_deleted is True
    assert record.version == 2
    assert record.deleted_at is not None
    assert payload == {"memory_id": memory_id, "version": 2, "operation": "DELETE"}


@pytest.mark.asyncio
async def test_reconciliation_detects_version_drift_and_enqueues_resync() -> None:
    tenant_id = f"tenant-memory-reconcile-{uuid.uuid4().hex[:8]}"
    thread_id = f"thread-{uuid.uuid4().hex}"
    user_id, memory_id, _ = await _committed_summary(tenant_id=tenant_id, thread_id=thread_id)
    index = RecordingVectorIndex()
    context = _context(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        operation_id="reconcile-summaries",
    )

    with tenant_scope(tenant_id):
        async with async_session_maker() as session:
            enqueued = await reconcile_summary_vectors(
                session=session,
                task_context=context,
                vector_index=index,
            )
            index.versions[(tenant_id, memory_id)] = 1
            converged = await reconcile_summary_vectors(
                session=session,
                task_context=context,
                vector_index=index,
            )
            await session.commit()

        async with async_session_maker() as verifier:
            events = list(
                (
                    await verifier.exec(
                        select(OutboxEvent).where(OutboxEvent.aggregate_id == str(memory_id))
                    )
                ).all()
            )

    assert enqueued == 1
    assert converged == 0
    assert len(events) == 2


def _execute(
    *,
    session: Session,
    envelope: TaskEnvelope,
    index: RecordingVectorIndex,
    attempt: int,
) -> dict[str, JsonValue]:
    return execute_memory_vector_sync_once(
        session=session,
        envelope=envelope,
        vector_index=index,
        attempt=attempt,
    )


def test_qdrant_failure_remains_retryable_and_later_recovers() -> None:
    tenant_id = f"tenant-memory-retry-{uuid.uuid4().hex[:8]}"
    index = RecordingVectorIndex(failures=1)

    with tenant_scope(tenant_id), sync_session_maker() as session:
        _, _, envelope = _stored_summary(
            session=session, tenant_id=tenant_id, thread_id=f"thread-{uuid.uuid4().hex}"
        )
        with pytest.raises(TransientTaskError):
            _execute(session=session, envelope=envelope, index=index, attempt=1)
        receipt = session.exec(
            select(TaskExecutionReceipt).where(
                TaskExecutionReceipt.idempotency_key == envelope.task_context.idempotency_key
            )
        ).one()
        retryable_status = receipt.status
        result = _execute(session=session, envelope=envelope, index=index, attempt=2)

    assert retryable_status == TaskReceiptStatus.RETRYABLE
    assert result["status"] == "indexed"
    assert len(index.upserts) == 1


def test_duplicate_vector_event_has_one_logical_effect() -> None:
    tenant_id = f"tenant-memory-duplicate-{uuid.uuid4().hex[:8]}"
    index = RecordingVectorIndex()

    with tenant_scope(tenant_id), sync_session_maker() as session:
        _, _, envelope = _stored_summary(
            session=session,
            tenant_id=tenant_id,
            thread_id=f"thread-{uuid.uuid4().hex}",
        )
        first = sync_memory_vector.run(
            envelope.to_message(),
            session=session,
            vector_index=index,
            dead_letter_publisher=NoopDeadLetterPublisher(),
        )
        second = sync_memory_vector.run(
            envelope.to_message(),
            session=session,
            vector_index=index,
            dead_letter_publisher=NoopDeadLetterPublisher(),
        )

    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert len(index.upserts) == 1


def test_stale_upsert_cannot_overwrite_newer_delete() -> None:
    tenant_id = f"tenant-memory-stale-{uuid.uuid4().hex[:8]}"
    thread_id = f"thread-{uuid.uuid4().hex}"

    with tenant_scope(tenant_id), sync_session_maker() as session:
        user_id, memory_id, stale_envelope = _stored_summary(
            session=session,
            tenant_id=tenant_id,
            thread_id=thread_id,
        )
        record = session.exec(
            select(InteractionSummary).where(InteractionSummary.id == memory_id)
        ).one()
        record.version = 2
        record.is_deleted = True
        session.add(record)
        session.commit()
        delete_context = _context(
            tenant_id=tenant_id,
            user_id=user_id,
            thread_id=thread_id,
            operation_id=f"summary:{memory_id}:v2:delete",
        )
        delete_envelope = TaskEnvelope(
            task_context=delete_context,
            payload=MemoryVectorSyncPayload(
                memory_id=memory_id,
                version=2,
                operation=MemoryVectorOperation.DELETE,
            ).model_dump(mode="json"),
        )

        index = RecordingVectorIndex()
        delete_result = _execute(
            session=session,
            envelope=delete_envelope,
            index=index,
            attempt=1,
        )
        stale_result = _execute(
            session=session,
            envelope=stale_envelope,
            index=index,
            attempt=1,
        )

    assert record.version == 2
    assert record.is_deleted is True
    assert delete_result["status"] == "deleted"
    assert stale_result["status"] == "stale_ignored"
    assert index.deletes == [(tenant_id, memory_id)]
    assert index.upserts == []


def test_qdrant_delete_failure_is_retryable_and_later_recovers() -> None:
    tenant_id = f"tenant-memory-delete-retry-{uuid.uuid4().hex[:8]}"
    thread_id = f"thread-{uuid.uuid4().hex}"
    index = RecordingVectorIndex(failures=1)

    with tenant_scope(tenant_id), sync_session_maker() as session:
        user_id, memory_id, _ = _stored_summary(
            session=session,
            tenant_id=tenant_id,
            thread_id=thread_id,
        )
        record = session.exec(
            select(InteractionSummary).where(InteractionSummary.id == memory_id)
        ).one()
        record.version = 2
        record.is_deleted = True
        session.add(record)
        session.commit()
        envelope = TaskEnvelope(
            task_context=_context(
                tenant_id=tenant_id,
                user_id=user_id,
                thread_id=thread_id,
                operation_id=f"summary:{memory_id}:v2:delete",
            ),
            payload=MemoryVectorSyncPayload(
                memory_id=memory_id,
                version=2,
                operation=MemoryVectorOperation.DELETE,
            ).model_dump(mode="json"),
        )

        with pytest.raises(TransientTaskError):
            _execute(session=session, envelope=envelope, index=index, attempt=1)
        result = _execute(session=session, envelope=envelope, index=index, attempt=2)

    assert result["status"] == "deleted"
    assert index.deletes == [(tenant_id, memory_id)]


def test_vector_sync_cannot_read_another_tenants_memory() -> None:
    tenant_a = f"tenant-memory-a-{uuid.uuid4().hex[:8]}"
    tenant_b = f"tenant-memory-b-{uuid.uuid4().hex[:8]}"
    with sync_session_maker() as session:
        with tenant_scope(tenant_a):
            _, memory_id, envelope_a = _stored_summary(
                session=session,
                tenant_id=tenant_a,
                thread_id=f"thread-{uuid.uuid4().hex}",
            )
        context_b = _context(
            tenant_id=tenant_b,
            user_id=envelope_a.task_context.user_id,
            thread_id=envelope_a.task_context.thread_id or "thread-b",
            operation_id=f"summary:{memory_id}:v1:upsert",
        )
        envelope_b = TaskEnvelope(
            task_context=context_b,
            payload=MemoryVectorSyncPayload(
                memory_id=memory_id,
                version=1,
                operation=MemoryVectorOperation.UPSERT,
            ).model_dump(mode="json"),
        )
        index = RecordingVectorIndex()
        with tenant_scope(tenant_b), pytest.raises(PermanentTaskError) as error:
            _execute(session=session, envelope=envelope_b, index=index, attempt=1)

    assert error.value.failure_code == "MEMORY_NOT_FOUND"
    assert index.upserts == []
    assert index.deletes == []


def test_vector_sync_payload_contains_identity_not_memory_text() -> None:
    payload: Mapping[str, JsonValue] = MemoryVectorSyncPayload(
        memory_id=123,
        version=4,
        operation=MemoryVectorOperation.UPSERT,
    ).model_dump(mode="json")

    assert payload == {"memory_id": 123, "version": 4, "operation": "UPSERT"}
