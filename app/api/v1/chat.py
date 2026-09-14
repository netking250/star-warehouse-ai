"""Authenticated chat and feedback transport adapters."""

import asyncio
import json
import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from opentelemetry import trace
from pydantic import BaseModel
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlmodel import desc, select

from app.api.v1.chat_utils import create_stream_metadata_message
from app.api.v1.schemas import ChatRequest
from app.context.pii_filter import log_pii_detection, pii_filter
from app.conversation.composition import (
    build_conversation_runtime,
    conversation_executor_is_available,
)
from app.conversation.contracts import (
    ConversationIdentity,
    ExecutorEventType,
    SubmitTurnCommand,
)
from app.conversation.runtime import ConversationBusyError, IdempotencyConflictError
from app.conversation.state_machine import RunStatus
from app.core.config import settings
from app.core.database import async_session_maker
from app.core.limiter import check_user_rate_limit, limiter
from app.core.security import (
    AuthContext,
    get_authorized_auth_context,
    get_authorized_user_id,
)
from app.core.utils import build_thread_id, utc_now
from app.models.memory import AgentConfigVersion
from app.observability.execution_logger import log_graph_execution, log_graph_node
from app.observability.metrics import (
    record_chat_error,
    record_chat_latency,
    record_chat_request,
    record_confidence_score,
    record_context_utilization,
    record_human_transfer,
    record_token_usage,
)
from app.observability.token_tracker import TokenTracker
from app.services.experiment_assigner import ExperimentAssigner
from app.services.online_eval import OnlineEvalService
from app.services.review_queue import ReviewQueueService
from app.task_runtime.context import build_task_context
from app.task_runtime.dispatch import dispatch_task
from app.tasks.observability_tasks import (
    build_chat_observability_payload,
    log_chat_observability,
)

router = APIRouter()
logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


async def _maybe_create_review_ticket(
    session: Any,
    thread_id: str,
    user_id: int,
    final_state: dict[str, Any],
    intent_category: str | None,
) -> None:
    confidence = final_state.get("confidence_score")
    needs_transfer = final_state.get("needs_human_transfer", False)
    transfer_reason = final_state.get("transfer_reason")
    service = ReviewQueueService(session)
    risk_score, risk_factors = await service.compute_risk_score(
        confidence=confidence,
        safety_blocked=needs_transfer,
        refund_amount=None,
        is_complaint=intent_category == "COMPLAINT",
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


async def _safe_vector_upsert(
    vector_manager: Any,
    user_id: int,
    thread_id: str,
    message_role: str,
    content: str,
    timestamp: str,
    intent: str | None = None,
) -> None:
    """Write derived vector memory without affecting authoritative runtime state."""
    try:
        await vector_manager.upsert_message(
            user_id=user_id,
            thread_id=thread_id,
            message_role=message_role,
            content=content,
            timestamp=timestamp,
            intent=intent,
        )
    except (OperationalError, OSError):
        logger.exception("Failed to upsert message to vector memory")


async def _resolve_agent_config_version_id(
    session: Any, agent_name: str | None, before_time: Any
) -> int | None:
    if not agent_name:
        return None
    result = await session.exec(
        select(AgentConfigVersion)
        .where(AgentConfigVersion.agent_name == agent_name)
        .where(AgentConfigVersion.created_at <= before_time)
        .order_by(desc(AgentConfigVersion.created_at))
        .limit(1)
    )
    version = result.one_or_none()
    return version.id if version else None


async def _log_post_chat_metrics(
    thread_id: str,
    user_id: int,
    final_state: dict[str, Any],
    node_latencies: dict[str, int],
    variant_id: int | None,
    total_latency_ms: int,
    langsmith_run_url: str | None,
    intent_category: str | None,
    query_text: str,
    variant_llm_model: str | None,
) -> None:
    """Persist legacy execution metrics outside the user-facing stream."""
    try:
        async with async_session_maker() as session:
            final_agent_name = final_state.get("current_agent")
            version_id = await _resolve_agent_config_version_id(
                session, final_agent_name, utc_now()
            )
            execution_id = await log_graph_execution(
                session=session,
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
                query=query_text,
            )
            for node_name, latency_ms in node_latencies.items():
                await log_graph_node(
                    session=session,
                    execution_id=execution_id,
                    node_name=node_name,
                    latency_ms=latency_ms,
                )
            if variant_id is not None:
                try:
                    from app.models.experiment import ExperimentMetrics

                    session.add(
                        ExperimentMetrics(
                            variant_id=variant_id,
                            user_id=user_id,
                            session_id=thread_id,
                            latency_ms=total_latency_ms,
                            token_count=final_state.get("context_tokens"),
                            confidence_score=final_state.get("confidence_score"),
                            needs_human_transfer=bool(
                                final_state.get("needs_human_transfer", False)
                            ),
                        )
                    )
                    await session.commit()
                except SQLAlchemyError:
                    logger.exception("Failed to record experiment metrics")
                    await session.rollback()
            await _maybe_create_review_ticket(
                session, thread_id, user_id, final_state, intent_category
            )
            if final_state.get("context_tokens") is not None:
                try:
                    response_text = str(final_state.get("answer", ""))
                    await TokenTracker(session).log_usage(
                        user_id=user_id,
                        thread_id=thread_id,
                        agent_type=final_agent_name or "unknown",
                        input_tokens=int(
                            final_state.get("model_input_tokens")
                            or final_state.get("context_tokens", 0)
                        ),
                        output_tokens=int(
                            final_state.get("model_output_tokens")
                            or max(1, len(response_text) // 4)
                        ),
                        query_text=query_text,
                        model_name=str(
                            final_state.get("model_name") or variant_llm_model or "unknown"
                        ),
                    )
                except (SQLAlchemyError, OperationalError):
                    logger.exception("Failed to log token usage to database")
    except Exception:
        logger.exception("Background post-chat metrics logging failed")


async def _run_shadow_in_background(
    request: Request,
    query: str,
    thread_id: str,
    user_id: int,
    production_result: dict[str, Any],
) -> None:
    """Run the existing non-authoritative shadow evaluator after completion."""
    from app.evaluation.shadow import ShadowOrchestrator

    if not settings.SHADOW_TESTING_ENABLED:
        return
    orchestrator = ShadowOrchestrator(sample_rate=settings.SHADOW_SAMPLE_RATE)
    if not orchestrator.should_sample(thread_id):
        return
    shadow_graph = getattr(request.app.state, "shadow_app_graph", None)
    production_graph = getattr(request.app.state, "app_graph", None)
    if shadow_graph is None or production_graph is None:
        return
    try:
        prod_result, shadow_result = await ShadowOrchestrator.run_shadow(
            query=query,
            production_graph=production_graph,
            shadow_graph=shadow_graph,
            session_id=f"shadow-{thread_id}",
        )
        comparison = ShadowOrchestrator.compare_results(
            thread_id=thread_id,
            production_result=prod_result,
            shadow_result=shadow_result,
        )
        llm = getattr(request.app.state, "llm", None)
        if llm is not None:
            comparison = await ShadowOrchestrator.compare_with_llm(comparison, llm)
        async with async_session_maker() as session:
            await ShadowOrchestrator.store_result(
                comparison=comparison,
                user_id=user_id,
                query=query,
                db_session=session,
            )
    except (RuntimeError, OSError):
        logger.exception("Background shadow test failed for thread %s", thread_id)


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _assign_variant(
    user_id: int,
) -> tuple[
    int | None,
    dict[str, Any] | None,
    str | None,
    int | None,
    bool | None,
]:
    async with async_session_maker() as session:
        config = await ExperimentAssigner().assign_with_config(
            str(user_id), "agent_prompt", db=session
        )
    if config is None:
        return None, None, None, None, None
    return (
        config.variant_id,
        config.memory_context_config,
        config.llm_model,
        config.retriever_top_k,
        config.reranker_enabled,
    )


@router.post("/chat")
@limiter.limit("60/minute")
async def chat(
    request: Request,
    chat_request: ChatRequest,
    auth_context: AuthContext = Depends(get_authorized_auth_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    """Submit one durable turn and stream its existing or newly executed run."""
    if not conversation_executor_is_available(request.app.state):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat service is not fully initialized. Please try again in a moment.",
        )
    runtime = build_conversation_runtime(request.app.state)
    user_id = auth_context.user_id
    conversation_id = build_thread_id(user_id, chat_request.thread_id)
    redis_client = getattr(request.app.state, "redis_client", None)
    if redis_client is not None:
        await check_user_rate_limit(redis_client, user_id, max_requests=10, window_seconds=60)

    pii_result = await pii_filter.afilter_text(chat_request.question)
    question = pii_result.redacted_text
    if pii_result.has_pii:
        log_pii_detection(
            user_id=user_id,
            thread_id=conversation_id,
            source="chat_input",
            detections=pii_result.detections,
        )

    with tracer.start_as_current_span("chat_endpoint") as span:
        span.set_attribute("chat.user_id", user_id)
        span.set_attribute("chat.thread_id", conversation_id)
        span_context = span.get_span_context()
        trace_id = format(span_context.trace_id, "032x") if span_context.is_valid else None
        identity = ConversationIdentity(
            tenant_id=auth_context.tenant_id,
            user_id=user_id,
            correlation_id=auth_context.correlation_id,
            trace_id=trace_id,
        )
        command = SubmitTurnCommand(
            conversation_id=conversation_id,
            question=question,
            idempotency_key=idempotency_key or str(uuid.uuid4()),
        )
        try:
            submission = await runtime.submit_turn(identity=identity, command=command)
        except (ConversationBusyError, IdempotencyConflictError) as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

        async def event_generator():
            accepted = await runtime.replay_events(
                identity=identity,
                conversation_id=conversation_id,
                run_id=submission.run_id,
            )
            if accepted:
                yield _sse(
                    {
                        "type": "runtime",
                        "event": str(accepted[0].event_type),
                        "sequence": accepted[0].sequence,
                        "conversation_id": conversation_id,
                        "turn_id": submission.turn_id,
                        "run_id": submission.run_id,
                    }
                )
            if not submission.created:
                snapshot = await runtime.get_run(
                    identity=identity,
                    conversation_id=conversation_id,
                    run_id=submission.run_id,
                )
                if snapshot.status is RunStatus.COMPLETED and snapshot.final_answer:
                    yield _sse({"token": snapshot.final_answer})
                yield _sse(
                    {
                        "type": "runtime",
                        "event": f"RUN_{snapshot.status}",
                        "conversation_id": conversation_id,
                        "turn_id": submission.turn_id,
                        "run_id": submission.run_id,
                        "replayed": True,
                    }
                )
                yield "data: [DONE]\n\n"
                return

            intent_category: str | None = None
            intent_service = getattr(request.app.state, "intent_service", None)
            if intent_service is not None:
                intent_result = await intent_service.recognize(
                    query=question,
                    session_id=conversation_id,
                    conversation_history=None,
                )
                if intent_result is not None:
                    intent_category = intent_result.primary_intent.value
            (
                variant_id,
                memory_context_config,
                variant_llm_model,
                variant_retriever_top_k,
                variant_reranker_enabled,
            ) = await _assign_variant(user_id)
            final_state: dict[str, Any] = {}
            node_latencies: dict[str, int] = {}
            langsmith_run_url: str | None = None
            start_time = time.monotonic()

            try:
                async for event in runtime.execute(
                    identity=identity,
                    submission=submission,
                    question=question,
                    intent_category=intent_category,
                    experiment_variant_id=variant_id,
                    memory_context_config=memory_context_config,
                    variant_llm_model=variant_llm_model,
                    variant_retriever_top_k=variant_retriever_top_k,
                    variant_reranker_enabled=variant_reranker_enabled,
                ):
                    if str(event.event_type) == str(ExecutorEventType.TOKEN):
                        yield _sse({"token": event.payload.get("token", "")})
                    elif str(event.event_type) == str(ExecutorEventType.METADATA):
                        raw_state = event.payload.get("final_state")
                        if isinstance(raw_state, dict):
                            final_state = raw_state
                        raw_latencies = event.payload.get("node_latencies")
                        if isinstance(raw_latencies, dict):
                            node_latencies = {
                                str(key): int(value) for key, value in raw_latencies.items()
                            }
                        raw_url = event.payload.get("langsmith_run_url")
                        langsmith_run_url = str(raw_url) if raw_url else None
                    elif event.durable:
                        yield _sse(
                            {
                                "type": "runtime",
                                "event": str(event.event_type),
                                "sequence": event.sequence,
                                "conversation_id": conversation_id,
                                "turn_id": submission.turn_id,
                                "run_id": submission.run_id,
                            }
                        )

                if final_state.get("confidence_score") is not None:
                    yield _sse(
                        create_stream_metadata_message(
                            confidence_score=final_state.get("confidence_score"),
                            confidence_signals=final_state.get("confidence_signals"),
                            needs_human_transfer=final_state.get("needs_human_transfer"),
                            transfer_reason=final_state.get("transfer_reason"),
                            audit_level=final_state.get("audit_level"),
                        )
                    )
                if trace_id:
                    yield _sse({"type": "metadata", "trace_id": trace_id})
                yield "data: [DONE]\n\n"

                total_latency_ms = int((time.monotonic() - start_time) * 1000)
                final_agent = final_state.get("current_agent")
                snapshot = await runtime.get_run(
                    identity=identity,
                    conversation_id=conversation_id,
                    run_id=submission.run_id,
                )
                vector_manager = getattr(request.app.state, "vector_manager", None)
                if vector_manager is not None and snapshot.status is RunStatus.COMPLETED:
                    asyncio.create_task(
                        _safe_vector_upsert(
                            vector_manager,
                            user_id,
                            conversation_id,
                            "user",
                            question,
                            utc_now().isoformat(),
                            intent_category,
                        )
                    )
                    if snapshot.final_answer:
                        asyncio.create_task(
                            _safe_vector_upsert(
                                vector_manager,
                                user_id,
                                conversation_id,
                                "assistant",
                                snapshot.final_answer,
                                utc_now().isoformat(),
                                intent_category,
                            )
                        )
                record_chat_request(intent_category=intent_category, final_agent=final_agent)
                record_chat_latency(
                    latency_seconds=total_latency_ms / 1000.0,
                    final_agent=final_agent,
                )
                if final_state.get("confidence_score") is not None:
                    record_confidence_score(float(final_state["confidence_score"]))
                if final_state.get("needs_human_transfer"):
                    record_human_transfer(reason=final_state.get("transfer_reason") or "unknown")
                if final_state.get("context_utilization") is not None:
                    record_context_utilization(float(final_state["context_utilization"]))
                if final_state.get("context_tokens") is not None:
                    record_token_usage(
                        tokens=int(final_state["context_tokens"]),
                        agent=final_agent,
                    )
                try:
                    task_context = build_task_context(
                        task_name="observability.log_chat_observability",
                        tenant_id=auth_context.tenant_id,
                        user_id=user_id,
                        correlation_id=auth_context.correlation_id,
                        trace_id=trace_id,
                        thread_id=conversation_id,
                        operation_id=submission.run_id,
                    )
                    payload = build_chat_observability_payload(
                        intent_category=intent_category,
                        final_state=final_state,
                        node_latencies=node_latencies,
                        total_latency_ms=total_latency_ms,
                        sanitized_question=question,
                        variant_id=variant_id,
                        variant_llm_model=variant_llm_model,
                        langsmith_run_url=langsmith_run_url,
                    )
                    dispatch_task(
                        log_chat_observability,
                        task_context=task_context,
                        payload=payload,
                        ignore_result=True,
                        retry=False,
                    )
                except Exception:
                    logger.exception("Failed to enqueue post-chat observability")
                asyncio.create_task(
                    _run_shadow_in_background(
                        request,
                        question,
                        conversation_id,
                        user_id,
                        {"result": final_state, "latency_ms": total_latency_ms},
                    )
                )
            except asyncio.CancelledError:
                logger.info("Chat stream cancelled", extra={"run_id": submission.run_id})
                raise
            except (ConnectionResetError, BrokenPipeError):
                await runtime.cancel_run(
                    identity=identity,
                    conversation_id=conversation_id,
                    run_id=submission.run_id,
                )
            except Exception:
                logger.exception("Unhandled conversation runtime stream error")
                record_chat_error(error_type="runtime")
                yield _sse({"error": "聊天服务出现内部错误，请稍后重试。"})
                if trace_id:
                    yield _sse({"type": "metadata", "trace_id": trace_id})
                yield "data: [DONE]\n\n"

        async def timed_event_generator():
            answer_started = False
            done_sent = False
            try:
                async with asyncio.timeout(settings.CHAT_STREAM_TIMEOUT_SECONDS):
                    async for chunk in event_generator():
                        answer_started = answer_started or '"token"' in chunk
                        done_sent = done_sent or "data: [DONE]" in chunk
                        yield chunk
            except TimeoutError:
                record_chat_error(error_type="timeout")
                await runtime.cancel_run(
                    identity=identity,
                    conversation_id=conversation_id,
                    run_id=submission.run_id,
                )
                if not answer_started:
                    yield _sse({"error": "服务响应超时，请稍后重试或联系人工客服。"})
                if not done_sent:
                    yield "data: [DONE]\n\n"

        headers = {"X-Trace-ID": trace_id} if trace_id else {}
        return StreamingResponse(
            timed_event_generator(),
            media_type="text/event-stream",
            headers=headers,
        )


_feedback_service = OnlineEvalService()


class SubmitFeedbackRequest(BaseModel):
    """User feedback attached to one conversation message index."""

    thread_id: str
    message_index: int
    sentiment: str
    comment: str | None = None
    category: str | None = None
    agent_type: str | None = None
    confidence_score: float | None = None


@router.post("/feedback")
async def submit_feedback(
    request: SubmitFeedbackRequest,
    current_user_id: int = Depends(get_authorized_user_id),
):
    """Persist authorized user feedback for an existing logical thread."""
    async with async_session_maker() as session:
        feedback = await _feedback_service.submit_feedback(
            db=session,
            user_id=current_user_id,
            thread_id=request.thread_id,
            message_index=request.message_index,
            sentiment=request.sentiment,
            comment=request.comment,
            category=request.category,
            agent_type=request.agent_type,
            confidence_score=request.confidence_score,
        )
    return {
        "success": True,
        "feedback_id": feedback.id,
        "score": feedback.score,
    }
