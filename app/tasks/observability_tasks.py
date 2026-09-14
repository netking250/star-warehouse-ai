"""Celery tasks for post-chat observability to keep the SSE critical path fast."""

from __future__ import annotations

import logging
from typing import Any

from asgiref.sync import async_to_sync
from opentelemetry import trace
from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.celery_app import celery_app
from app.context.pii_filter import pii_filter
from app.core.config import settings
from app.models.memory import AgentConfigVersion
from app.models.observability import GraphExecutionLog, GraphNodeLog
from app.observability.metrics import (
    record_chat_latency,
    record_confidence_score,
    record_context_utilization,
    record_human_transfer,
    record_token_usage,
)
from app.observability.token_tracker import TokenTracker
from app.services.review_queue import ReviewQueueService
from app.task_runtime.binding import task_execution_scope
from app.task_runtime.envelope import TaskEnvelope

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

_OBSERVABILITY_STATE_FIELDS = frozenset(
    {
        "answer",
        "confidence_score",
        "context_tokens",
        "context_utilization",
        "current_agent",
        "needs_human_transfer",
        "transfer_reason",
    }
)


class ChatObservabilityPayload(BaseModel):
    """Minimal PII-safe business payload persisted after a chat request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    intent_category: str | None
    final_state: dict[str, JsonValue]
    node_latencies: dict[str, int]
    total_latency_ms: int = Field(ge=0)
    sanitized_question: str
    variant_id: int | None
    variant_llm_model: str | None
    langsmith_run_url: str | None

    @field_validator("sanitized_question")
    @classmethod
    def _reject_raw_pii(cls, value: str) -> str:
        if pii_filter.filter_text(value).has_pii:
            raise ValueError("sanitized_question still contains supported PII")
        return value

    @model_validator(mode="after")
    def _reject_raw_pii_in_state(self) -> ChatObservabilityPayload:
        def contains_pii(value: JsonValue) -> bool:
            if isinstance(value, str):
                return pii_filter.filter_text(value).has_pii
            if isinstance(value, list):
                return any(contains_pii(item) for item in value)
            if isinstance(value, dict):
                return any(contains_pii(item) for item in value.values())
            return False

        if any(contains_pii(value) for value in self.final_state.values()):
            raise ValueError("final_state still contains supported PII")
        return self


def build_chat_observability_payload(
    *,
    intent_category: str | None,
    final_state: dict[str, Any],
    node_latencies: dict[str, int],
    total_latency_ms: int,
    sanitized_question: str,
    variant_id: int | None,
    variant_llm_model: str | None,
    langsmith_run_url: str | None,
) -> ChatObservabilityPayload:
    """Build the minimal sanitized payload allowed across the telemetry boundary."""
    safe_state: dict[str, JsonValue] = {}
    for key in _OBSERVABILITY_STATE_FIELDS:
        value = final_state.get(key)
        if isinstance(value, str):
            value = pii_filter.filter_text(value).redacted_text
        if value is None or isinstance(value, (str, int, float, bool, list, dict)):
            safe_state[key] = value
    return ChatObservabilityPayload(
        intent_category=intent_category,
        final_state=safe_state,
        node_latencies=node_latencies,
        total_latency_ms=total_latency_ms,
        sanitized_question=sanitized_question,
        variant_id=variant_id,
        variant_llm_model=variant_llm_model,
        langsmith_run_url=langsmith_run_url,
    )


async def _async_log_chat_observability(
    thread_id: str,
    user_id: int,
    intent_category: str | None,
    final_state: dict[str, Any],
    node_latencies: dict[str, int],
    total_latency_ms: int,
    sanitized_question: str,
    variant_id: int | None,
    variant_llm_model: str | None,
    langsmith_run_url: str | None,
    trace_id: str | None,
) -> int | None:
    """Async helper for observability logging using AsyncSession."""
    # ``async_to_sync`` creates a fresh event loop per invocation. A pooled
    # asyncpg connection cannot safely move between those loops, so this task
    # owns a non-pooled engine for exactly one invocation.
    task_engine = create_async_engine(
        settings.DATABASE_URL,
        poolclass=NullPool,
        connect_args={
            "timeout": settings.DB_CONNECT_TIMEOUT,
            "server_settings": {
                "application_name": f"{settings.SERVICE_NAME}-celery",
                "jit": "off",
            },
        },
    )
    task_session_maker = async_sessionmaker(
        task_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    session = task_session_maker()
    try:
        final_agent_name = final_state.get("current_agent")

        # Resolve agent config version
        version_id = None
        if final_agent_name:
            result = await session.exec(
                select(AgentConfigVersion)
                .where(AgentConfigVersion.agent_name == final_agent_name)
                .order_by(desc(AgentConfigVersion.created_at))
                .limit(1)
            )
            version = result.one_or_none()
            version_id = version.id if version else None

        # Log graph execution
        log = GraphExecutionLog(
            thread_id=thread_id,
            user_id=user_id,
            intent_category=intent_category,
            final_agent=final_agent_name,
            confidence_score=final_state.get("confidence_score"),
            needs_human_transfer=bool(final_state.get("needs_human_transfer", False)),
            total_latency_ms=total_latency_ms,
            agent_config_version_id=version_id,
            context_tokens=final_state.get("context_tokens"),
            context_utilization=final_state.get("context_utilization"),
            langsmith_run_url=langsmith_run_url,
            query=sanitized_question,
            trace_id=trace_id,
        )
        session.add(log)
        await session.commit()
        await session.refresh(log)
        execution_id = log.id
        assert execution_id is not None

        # Log per-node latencies
        for node_name, latency_ms in node_latencies.items():
            node_log = GraphNodeLog(
                execution_id=execution_id,
                node_name=node_name,
                latency_ms=latency_ms,
            )
            session.add(node_log)
        await session.commit()

        # Experiment metrics
        if variant_id is not None:
            try:
                from app.models.experiment import ExperimentMetrics

                metrics = ExperimentMetrics(
                    variant_id=variant_id,
                    user_id=user_id,
                    session_id=thread_id,
                    latency_ms=total_latency_ms,
                    token_count=final_state.get("context_tokens"),
                    confidence_score=final_state.get("confidence_score"),
                    needs_human_transfer=bool(final_state.get("needs_human_transfer", False)),
                )
                session.add(metrics)
                await session.commit()
            except SQLAlchemyError:
                logger.exception("Failed to record experiment metrics")
                await session.rollback()

        # Review ticket for high-risk conversations
        confidence = final_state.get("confidence_score")
        needs_transfer = final_state.get("needs_human_transfer", False)
        transfer_reason = final_state.get("transfer_reason")
        is_complaint = intent_category == "COMPLAINT"

        service = ReviewQueueService(session)
        risk_score, risk_factors = await service.compute_risk_score(
            confidence=confidence,
            safety_blocked=needs_transfer,
            refund_amount=None,
            is_complaint=is_complaint,
        )
        if risk_score >= 0.5:
            try:
                await service.create_ticket(
                    conversation_id=thread_id,
                    user_id=user_id,
                    risk_score=risk_score,
                    risk_factors=risk_factors,
                    confidence_score=confidence,
                    transfer_reason=transfer_reason,
                )
            except (SQLAlchemyError, OperationalError):
                logger.exception("Failed to create review ticket for thread %s", thread_id)

        if final_state.get("context_tokens") is not None:
            try:
                token_tracker = TokenTracker(session)
                raw_response_text = final_state.get("answer")
                response_text = raw_response_text if isinstance(raw_response_text, str) else ""
                estimated_output_tokens = max(1, len(response_text) // 4)
                await token_tracker.log_usage(
                    user_id=user_id,
                    thread_id=thread_id,
                    agent_type=final_agent_name or "unknown",
                    input_tokens=int(final_state.get("context_tokens", 0)),
                    output_tokens=estimated_output_tokens,
                    query_text=sanitized_question,
                    model_name=variant_llm_model or "unknown",
                )
            except (SQLAlchemyError, OperationalError):
                logger.exception("Failed to log token usage to database")

    finally:
        await session.close()
        await task_engine.dispose()

    return execution_id


@celery_app.task(
    bind=True,
    name="observability.log_chat_observability",
    ignore_result=True,
    max_retries=2,
    default_retry_delay=30,
)
def log_chat_observability(
    self,
    envelope: dict[str, object],
) -> dict[str, Any]:
    """Persist execution logs, metrics, review tickets, and token usage asynchronously.

    This task is enqueued from the chat endpoint after SSE streaming completes so
    that the HTTP response is not blocked by observability I/O.
    """
    task_envelope = TaskEnvelope.from_message(envelope)
    task_context = task_envelope.task_context
    payload = ChatObservabilityPayload.model_validate(task_envelope.payload)
    if task_context.thread_id is None:
        raise ValueError("Observability tasks require thread_id in TaskContext")
    task_id = getattr(self.request, "id", None)
    with task_execution_scope(
        task_context,
        task_name="celery.log_chat_observability",
        task_id=task_id,
    ):
        try:
            execution_id = async_to_sync(_async_log_chat_observability)(
                thread_id=task_context.thread_id,
                user_id=task_context.user_id,
                intent_category=payload.intent_category,
                final_state=payload.final_state,
                node_latencies=payload.node_latencies,
                total_latency_ms=payload.total_latency_ms,
                sanitized_question=payload.sanitized_question,
                variant_id=payload.variant_id,
                variant_llm_model=payload.variant_llm_model,
                langsmith_run_url=payload.langsmith_run_url,
                trace_id=task_context.trace_id,
            )

            final_agent_name = payload.final_state.get("current_agent")

            record_chat_latency(
                latency_seconds=payload.total_latency_ms / 1000.0,
                final_agent=str(final_agent_name) if final_agent_name is not None else None,
            )
            confidence_score = payload.final_state.get("confidence_score")
            if isinstance(confidence_score, (int, float)):
                record_confidence_score(float(confidence_score))
            if payload.final_state.get("needs_human_transfer"):
                transfer_reason = payload.final_state.get("transfer_reason")
                record_human_transfer(
                    reason=str(transfer_reason) if transfer_reason is not None else "unknown"
                )
            context_utilization = payload.final_state.get("context_utilization")
            if isinstance(context_utilization, (int, float)):
                record_context_utilization(float(context_utilization))
            context_tokens = payload.final_state.get("context_tokens")
            if isinstance(context_tokens, (int, float)):
                record_token_usage(
                    tokens=int(context_tokens),
                    agent=str(final_agent_name) if final_agent_name is not None else None,
                )

            return {"status": "success", "execution_id": execution_id}
        except (SQLAlchemyError, OperationalError) as exc:
            logger.exception("Observability logging failed for thread %s", task_context.thread_id)
            try:
                raise self.retry(exc=exc)
            except self.MaxRetriesExceededError:
                return {"status": "failed", "message": "Observability logging max retries exceeded"}
