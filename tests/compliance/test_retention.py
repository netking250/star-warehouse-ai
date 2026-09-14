"""Targeted bounded retention behavior tests."""

import logging
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlmodel import col, select

from app.compliance.retention import RetentionExecutionDisabledError, RetentionExecutor
from app.core.config import settings
from app.core.tenancy import tenant_storage_path
from app.models.evaluation import MessageFeedback
from app.models.knowledge_document import KnowledgeDocument
from app.models.user import User
from app.observability.metrics import RETENTION_RECORDS_PROCESSED_TOTAL, RETENTION_RUNS_TOTAL


async def _feedback(
    session, tenant_id: str, *, created_at: datetime, suffix: str
) -> MessageFeedback:
    user = User(
        tenant_id=tenant_id,
        username=f"retention-{suffix}",
        password_hash=User.hash_password("test-password"),
        email=f"retention-{suffix}@example.com",
        full_name="Retention Test User",
    )
    session.add(user)
    await session.flush()
    assert user.id is not None
    feedback = MessageFeedback(
        tenant_id=tenant_id,
        user_id=user.id,
        thread_id=f"thread-{suffix}",
        message_index=0,
        score=1,
        created_at=created_at,
    )
    session.add(feedback)
    await session.flush()
    return feedback


@pytest.mark.asyncio
async def test_retention_dry_run_reports_eligible_without_mutation(
    db_session, tenant_context: str
) -> None:
    now = datetime(2026, 9, 14, tzinfo=UTC)
    old = await _feedback(
        db_session, tenant_context, created_at=now - timedelta(days=366), suffix="dry"
    )

    result = await RetentionExecutor().run(
        db_session,
        dataset="message_feedbacks",
        tenant_id=tenant_context,
        now=now,
        dry_run=True,
        correlation_id="retention-dry-run",
        actor_user_id=None,
    )

    assert result.eligible_count == 1
    assert result.processed_count == 0
    assert await db_session.get(MessageFeedback, old.id) is not None


@pytest.mark.asyncio
async def test_retention_processes_only_expired_records_and_respects_batch(
    db_session, tenant_context: str
) -> None:
    now = datetime(2026, 9, 14, tzinfo=UTC)
    expired = [
        await _feedback(
            db_session,
            tenant_context,
            created_at=now - timedelta(days=366, minutes=index),
            suffix=f"old-{index}",
        )
        for index in range(3)
    ]
    recent = await _feedback(
        db_session, tenant_context, created_at=now - timedelta(days=364), suffix="recent"
    )
    runs_before = RETENTION_RUNS_TOTAL.labels(result="success")._value.get()
    processed_before = RETENTION_RECORDS_PROCESSED_TOTAL.labels(
        dataset="message_feedbacks", result="success"
    )._value.get()

    first = await RetentionExecutor().run(
        db_session,
        dataset="message_feedbacks",
        tenant_id=tenant_context,
        now=now,
        dry_run=False,
        correlation_id="retention-execute",
        actor_user_id=None,
        batch_limit=2,
    )
    await db_session.flush()

    assert first.processed_count == 2
    assert await db_session.get(MessageFeedback, recent.id) is not None
    remaining_old = list(
        (
            await db_session.exec(
                select(MessageFeedback).where(
                    col(MessageFeedback.id).in_([item.id for item in expired])
                )
            )
        ).all()
    )
    assert len(remaining_old) == 1

    second = await RetentionExecutor().run(
        db_session,
        dataset="message_feedbacks",
        tenant_id=tenant_context,
        now=now,
        dry_run=False,
        correlation_id="retention-repeat",
        actor_user_id=None,
        batch_limit=2,
    )
    third = await RetentionExecutor().run(
        db_session,
        dataset="message_feedbacks",
        tenant_id=tenant_context,
        now=now,
        dry_run=False,
        correlation_id="retention-idempotent",
        actor_user_id=None,
        batch_limit=2,
    )
    assert second.processed_count == 1
    assert third.processed_count == 0
    assert RETENTION_RUNS_TOTAL.labels(result="success")._value.get() == runs_before + 3
    assert (
        RETENTION_RECORDS_PROCESSED_TOTAL.labels(
            dataset="message_feedbacks", result="success"
        )._value.get()
        == processed_before + 3
    )


@pytest.mark.asyncio
async def test_retention_tenant_predicate_and_kill_switch(
    db_session, tenant_context: str, monkeypatch
) -> None:
    now = datetime(2026, 9, 14, tzinfo=UTC)
    await _feedback(db_session, tenant_context, created_at=now - timedelta(days=366), suffix="kill")
    monkeypatch.setattr(settings, "RETENTION_EXECUTION_ENABLED", False)

    with pytest.raises(RetentionExecutionDisabledError):
        await RetentionExecutor().run(
            db_session,
            dataset="message_feedbacks",
            tenant_id=tenant_context,
            now=now,
            dry_run=False,
            correlation_id="retention-disabled",
            actor_user_id=None,
        )

    count = len((await db_session.exec(select(MessageFeedback))).all())
    assert count == 1


@pytest.mark.asyncio
async def test_retention_cannot_delete_another_tenants_eligible_record(
    db_session, tenant_context: str, test_maintenance_engine
) -> None:
    now = datetime(2026, 9, 14, tzinfo=UTC)
    other_tenant = f"retention-other-{uuid.uuid4().hex[:8]}"
    async with test_maintenance_engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO tenants (id, slug, display_name, status) "
                "VALUES (:id, :id, 'Other retention tenant', 'active')"
            ),
            {"id": other_tenant},
        )
        other_user = (
            await connection.execute(
                text(
                    "INSERT INTO users (tenant_id, username, password_hash, email, full_name, "
                    "is_admin, role, is_active) VALUES (:tenant_id, :username, 'hash', :email, "
                    "'Other User', false, 'customer', true) RETURNING id"
                ),
                {
                    "tenant_id": other_tenant,
                    "username": f"other-{other_tenant}",
                    "email": f"{other_tenant}@example.com",
                },
            )
        ).scalar_one()
        other_feedback = (
            await connection.execute(
                text(
                    "INSERT INTO message_feedbacks (tenant_id, user_id, thread_id, message_index, "
                    "score, created_at) VALUES (:tenant_id, :user_id, 'other-thread', 0, 1, "
                    ":created_at) RETURNING id"
                ),
                {
                    "tenant_id": other_tenant,
                    "user_id": other_user,
                    "created_at": now - timedelta(days=366),
                },
            )
        ).scalar_one()

    try:
        result = await RetentionExecutor().run(
            db_session,
            dataset="message_feedbacks",
            tenant_id=tenant_context,
            now=now,
            dry_run=False,
            correlation_id="retention-cross-tenant",
            actor_user_id=None,
        )
        await db_session.flush()
        async with test_maintenance_engine.connect() as connection:
            remaining = (
                await connection.execute(
                    text("SELECT count(*) FROM message_feedbacks WHERE id = :id"),
                    {"id": other_feedback},
                )
            ).scalar_one()
        assert result.processed_count == 0
        assert remaining == 1
    finally:
        async with test_maintenance_engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM message_feedbacks WHERE tenant_id = :tenant_id"),
                {"tenant_id": other_tenant},
            )
            await connection.execute(
                text("DELETE FROM users WHERE tenant_id = :tenant_id"),
                {"tenant_id": other_tenant},
            )
            await connection.execute(
                text("DELETE FROM tenants WHERE id = :tenant_id"),
                {"tenant_id": other_tenant},
            )


@pytest.mark.asyncio
async def test_external_object_cleanup_is_tenant_safe_and_missing_is_idempotent(
    db_session, tenant_context: str, tmp_path, monkeypatch
) -> None:
    now = datetime(2026, 9, 14, tzinfo=UTC)
    monkeypatch.setattr(settings, "KNOWLEDGE_UPLOAD_DIR", str(tmp_path / "knowledge"))
    path = tenant_storage_path(settings.KNOWLEDGE_UPLOAD_DIR, "expired.txt")
    path.parent.mkdir(parents=True)
    path.write_text("tenant knowledge", encoding="utf-8")
    document = KnowledgeDocument(
        storage_path=str(path),
        filename="expired.txt",
        created_at=now - timedelta(days=366),
    )
    db_session.add(document)
    await db_session.flush()

    result = await RetentionExecutor().run(
        db_session,
        dataset="knowledge_documents",
        tenant_id=tenant_context,
        now=now,
        dry_run=False,
        correlation_id="retention-object",
        actor_user_id=None,
    )
    await db_session.flush()

    assert result.processed_count == 1
    assert not path.exists()
    assert await db_session.get(KnowledgeDocument, document.id) is None


@pytest.mark.asyncio
async def test_retention_failure_is_logged_and_counted(
    db_session, tenant_context: str, tmp_path, monkeypatch, caplog
) -> None:
    now = datetime(2026, 9, 14, tzinfo=UTC)
    monkeypatch.setattr(settings, "KNOWLEDGE_UPLOAD_DIR", str(tmp_path / "knowledge"))
    document = KnowledgeDocument(
        storage_path=str(tmp_path / "outside.txt"),
        filename="outside.txt",
        created_at=now - timedelta(days=366),
    )
    db_session.add(document)
    await db_session.flush()
    caplog.set_level(logging.ERROR)
    failures_before = RETENTION_RUNS_TOTAL.labels(result="failure")._value.get()

    with pytest.raises(Exception, match="escaped the current tenant"):
        await RetentionExecutor().run(
            db_session,
            dataset="knowledge_documents",
            tenant_id=tenant_context,
            now=now,
            dry_run=False,
            correlation_id="retention-failure",
            actor_user_id=None,
        )

    assert "Retention execution failed" in caplog.text
    assert RETENTION_RUNS_TOTAL.labels(result="failure")._value.get() == failures_before + 1
    assert await db_session.get(KnowledgeDocument, document.id) is not None
