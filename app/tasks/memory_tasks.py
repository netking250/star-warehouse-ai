"""
Memory extraction Celery tasks.
"""

from __future__ import annotations

import logging
from typing import Any

from asgiref.sync import async_to_sync
from pydantic import BaseModel, ConfigDict, JsonValue, field_validator, model_validator
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from app.celery_app import celery_app
from app.celery_tracing import setup_celery_langsmith_tracing
from app.context.pii_filter import pii_filter
from app.core.config import settings
from app.core.database import sync_session_maker
from app.memory.consistency import MemoryVectorIndex, apply_memory_vector_sync
from app.memory.extractor import FactExtractor
from app.memory.vector_manager import VectorMemoryManager
from app.models.memory import UserFact
from app.task_runtime.binding import task_execution_scope
from app.task_runtime.dead_letter import CeleryDeadLetterPublisher, DeadLetterPublisher
from app.task_runtime.envelope import TaskEnvelope
from app.task_runtime.reliability import consume_external_task
from app.task_runtime.system import system_task_handler

logger = logging.getLogger(__name__)


class ExtractFactsPayload(BaseModel):
    """Sanitized conversation data required for asynchronous fact extraction."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    history: list[dict[str, JsonValue]]
    question: str
    answer: str

    @field_validator("question", "answer")
    @classmethod
    def _reject_raw_pii(cls, value: str) -> str:
        if pii_filter.filter_text(value).has_pii:
            raise ValueError("Fact extraction payload still contains supported PII")
        return value

    @model_validator(mode="after")
    def _reject_raw_pii_in_history(self) -> ExtractFactsPayload:
        for message in self.history:
            if any(
                isinstance(value, str) and pii_filter.filter_text(value).has_pii
                for value in message.values()
            ):
                raise ValueError("Fact extraction history still contains supported PII")
        return self


def build_extract_facts_payload(
    *, history: list[dict[str, Any]], question: str, answer: str
) -> ExtractFactsPayload:
    """Redact conversation text before crossing the Celery boundary."""
    safe_history: list[dict[str, JsonValue]] = []
    for message in history:
        safe_message: dict[str, JsonValue] = {}
        for key, value in message.items():
            safe_message[key] = (
                pii_filter.filter_text(value).redacted_text if isinstance(value, str) else value
            )
        safe_history.append(safe_message)
    return ExtractFactsPayload(
        history=safe_history,
        question=pii_filter.filter_text(question).redacted_text,
        answer=pii_filter.filter_text(answer).redacted_text,
    )


def _save_facts_body(
    self, user_id: int, thread_id: str, facts: list[dict[str, Any]], session: Session
) -> dict[str, Any]:
    try:
        saved_count = 0
        for fact_data in facts:
            existing = session.exec(
                select(UserFact)
                .where(
                    UserFact.user_id == user_id,
                    UserFact.source_thread_id == thread_id,
                    UserFact.fact_type == fact_data["fact_type"],
                    UserFact.content == fact_data["content"],
                )
                .limit(1)
            ).one_or_none()
            if existing:
                continue
            fact = UserFact(
                user_id=user_id,
                fact_type=fact_data["fact_type"],
                content=fact_data["content"],
                confidence=fact_data["confidence"],
                source_thread_id=thread_id,
            )
            session.add(fact)
            saved_count += 1
        session.commit()
    except (SQLAlchemyError, OSError) as exc:
        logger.exception("Failed to save facts for user_id=%s thread_id=%s", user_id, thread_id)
        session.rollback()
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"status": "failed", "message": "保存事实失败，已达到最大重试次数"}

    return {"status": "success", "facts_extracted": saved_count}


@celery_app.task(
    bind=True,
    name="memory.extract_and_save_facts",
    max_retries=2,
    default_retry_delay=60,
)
def extract_and_save_facts(
    self,
    envelope: dict[str, object],
    session=None,
    extractor=None,
) -> dict[str, Any]:
    setup_celery_langsmith_tracing()
    task_envelope = TaskEnvelope.from_message(envelope)
    task_context = task_envelope.task_context
    payload = ExtractFactsPayload.model_validate(task_envelope.payload)
    if task_context.thread_id is None:
        raise ValueError("Fact extraction tasks require thread_id in TaskContext")

    task_id = getattr(self.request, "id", None)
    with task_execution_scope(
        task_context,
        task_name="celery.memory.extract_and_save_facts",
        task_id=task_id,
    ):
        effective_extractor = extractor or FactExtractor()
        try:
            facts = async_to_sync(effective_extractor.extract_facts)(
                task_context.user_id,
                task_context.thread_id,
                payload.history,
                payload.answer,
                payload.question,
            )
        except (OSError, RuntimeError) as exc:
            logger.exception(
                "Fact extraction failed for user_id=%s thread_id=%s",
                task_context.user_id,
                task_context.thread_id,
            )
            try:
                raise self.retry(exc=exc)
            except self.MaxRetriesExceededError:
                return {"status": "failed", "message": "事实提取失败，已达到最大重试次数"}

        if session is None:
            with sync_session_maker() as task_session:
                return _save_facts_body(
                    self,
                    task_context.user_id,
                    task_context.thread_id,
                    facts,
                    task_session,
                )
        return _save_facts_body(
            self,
            task_context.user_id,
            task_context.thread_id,
            facts,
            session,
        )


@celery_app.task(name="memory.prune_vector_memory")
@system_task_handler("memory.prune_vector_memory")
def prune_vector_memory() -> dict[str, Any]:
    manager = VectorMemoryManager()
    try:
        async_to_sync(manager.prune_old_messages)(settings.MEMORY_RETENTION_DAYS)
        async_to_sync(manager.aclose)()
        return {"status": "success", "pruned": True}
    except (OSError, RuntimeError):
        logger.exception("Vector memory pruning failed")
        return {"status": "failed", "message": "向量记忆清理失败"}


@celery_app.task(
    bind=True,
    name="memory.sync_vector",
    ignore_result=True,
    max_retries=3,
    acks_late=True,
    acks_on_failure_or_timeout=False,
    reject_on_worker_lost=True,
)
def sync_memory_vector(
    self,
    envelope: dict[str, object],
    session: Session | None = None,
    vector_index: MemoryVectorIndex | None = None,
    dead_letter_publisher: DeadLetterPublisher | None = None,
) -> dict[str, JsonValue]:
    """Project authoritative memory into Qdrant through reliable delivery."""
    if vector_index is None:
        owned_manager: VectorMemoryManager | None = VectorMemoryManager()
        effective_index: MemoryVectorIndex = owned_manager
    else:
        owned_manager = None
        effective_index = vector_index
    publisher = dead_letter_publisher or CeleryDeadLetterPublisher(celery_app)

    def run(task_session: Session) -> dict[str, JsonValue]:
        return consume_external_task(
            task=self,
            raw_envelope=envelope,
            handler="memory.sync_vector",
            operation=lambda: apply_memory_vector_sync(
                session=task_session,
                envelope=TaskEnvelope.from_message(envelope),
                vector_index=effective_index,
            ),
            session=task_session,
            dead_letter_publisher=publisher,
        )

    try:
        if session is None:
            with sync_session_maker() as task_session:
                return run(task_session)
        return run(session)
    finally:
        if owned_manager is not None:
            async_to_sync(owned_manager.aclose)()
