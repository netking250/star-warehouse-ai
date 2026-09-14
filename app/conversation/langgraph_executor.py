"""LangGraph adapter behind the conversation executor Port."""

from __future__ import annotations

import contextlib
import time
from collections.abc import AsyncIterator
from typing import Any, Protocol

from langchain_core.runnables import RunnableConfig
from langchain_core.tracers.context import tracing_v2_enabled
from langgraph.types import Command

from app.conversation.contracts import (
    ConversationExecutor,
    ExecutionRequest,
    ExecutorEvent,
    ExecutorEventType,
)
from app.core.config import settings
from app.core.tracing import build_llm_config, is_langsmith_tracing_enabled
from app.models.state import AgentState, make_agent_state
from app.observability.metrics import record_node_latency


class LangGraphEventSource(Protocol):
    """Minimum graph surface required by the executor adapter."""

    def astream_events(
        self,
        input: AgentState,
        config: RunnableConfig,
        *,
        version: str,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream graph execution events."""
        ...


_ANSWER_NODES = frozenset(
    {
        "router_node",
        "policy_agent",
        "order_agent",
        "logistics",
        "account",
        "payment",
        "product",
        "cart",
        "complaint",
        "synthesis_node",
    }
)
_FINAL_STATE_KEYS = frozenset(
    {
        "answer",
        "audit_level",
        "confidence_score",
        "confidence_signals",
        "context_tokens",
        "context_utilization",
        "current_agent",
        "needs_human_transfer",
        "transfer_reason",
        "model_provider",
        "model_name",
        "model_input_tokens",
        "model_output_tokens",
        "model_total_tokens",
    }
)


class LangGraphConversationExecutor(ConversationExecutor):
    """Translate existing LangGraph events into transport-independent executor events."""

    def __init__(self, graph: LangGraphEventSource) -> None:
        self._graph = graph

    async def execute(self, request: ExecutionRequest) -> AsyncIterator[ExecutorEvent]:
        """Execute one durable run using a run-isolated checkpoint namespace."""
        config: RunnableConfig = build_llm_config(
            user_id=request.user_id,
            thread_id=request.conversation_id,
            intent=request.intent_category,
            extra_metadata={
                "trace_id": request.trace_id,
                "turn_id": request.turn_id,
                "run_id": request.run_id,
            },
            tags=["conversation_runtime"],
        )
        config["configurable"] = {
            "thread_id": request.conversation_id,
            "checkpoint_ns": f"{settings.CHECKPOINT_SCHEMA_VERSION}:{request.run_id}",
        }
        initial_state = make_agent_state(
            question=request.question,
            user_id=request.user_id,
            thread_id=request.conversation_id,
            tenant_id=request.tenant_id,
            correlation_id=request.correlation_id,
            trace_id=request.trace_id,
            history=[{"role": "user", "content": request.question}],
            experiment_variant_id=request.experiment_variant_id,
            memory_context_config=request.memory_context_config,
            variant_llm_model=request.variant_llm_model,
            variant_retriever_top_k=request.variant_retriever_top_k,
            variant_reranker_enabled=request.variant_reranker_enabled,
        )
        final_state: dict[str, Any] = {}
        streamed_chunks: list[str] = []
        streamed_any_answer = False
        sent_answers: set[str] = set()
        node_start_times: dict[str, float] = {}
        node_latencies: dict[str, int] = {}
        langsmith_run_url: str | None = None

        tracing_context = (
            tracing_v2_enabled(project_name=settings.LANGSMITH_PROJECT)
            if is_langsmith_tracing_enabled()
            else contextlib.nullcontext(None)
        )
        with tracing_context as callback:
            async for event in self._graph.astream_events(initial_state, config, version="v2"):
                kind = event.get("event")
                metadata = event.get("metadata")
                event_metadata = metadata if isinstance(metadata, dict) else {}
                node_name = str(event_metadata.get("langgraph_node", ""))
                event_run_id = str(event.get("run_id", ""))

                if kind == "on_chain_start" and node_name:
                    node_start_times[event_run_id] = time.monotonic()
                    continue

                if kind == "on_chat_model_stream":
                    tags = set(event_metadata.get("tags", [])) | set(event.get("tags", []))
                    if (
                        node_name == "router_node"
                        or "confidence_eval" in tags
                        or "internal" in tags
                        or "user_visible" not in tags
                    ):
                        continue
                    data = event.get("data")
                    chunk = data.get("chunk") if isinstance(data, dict) else None
                    content = getattr(chunk, "content", None)
                    if content:
                        text = str(content)
                        streamed_any_answer = True
                        streamed_chunks.append(text)
                        yield ExecutorEvent(ExecutorEventType.TOKEN, {"token": text})
                    continue

                if kind != "on_chain_end":
                    continue
                if event_run_id in node_start_times and node_name:
                    latency_ms = int((time.monotonic() - node_start_times.pop(event_run_id)) * 1000)
                    node_latencies[node_name] = node_latencies.get(node_name, 0) + latency_ms
                    record_node_latency(node_name=node_name, latency_seconds=latency_ms / 1000.0)

                data = event.get("data")
                raw_output = data.get("output", {}) if isinstance(data, dict) else {}
                if isinstance(raw_output, Command):
                    output = raw_output.update
                elif isinstance(raw_output, dict):
                    output = raw_output
                else:
                    output = {}
                for key in _FINAL_STATE_KEYS:
                    if key in output:
                        final_state[key] = output[key]
                answer = output.get("answer")
                if isinstance(answer, dict):
                    answer = str(answer)
                if (
                    node_name in _ANSWER_NODES
                    and answer
                    and str(answer) not in sent_answers
                    and not streamed_any_answer
                ):
                    text = str(answer)
                    sent_answers.add(text)
                    yield ExecutorEvent(ExecutorEventType.TOKEN, {"token": text})

            if callback is not None:
                get_run_url = getattr(callback, "get_run_url", None)
                if callable(get_run_url):
                    try:
                        langsmith_run_url = str(get_run_url())
                    except Exception:
                        langsmith_run_url = None

        final_answer = str(final_state.get("answer") or "")
        if not final_answer and streamed_chunks:
            final_answer = "".join(streamed_chunks)
        final_state["answer"] = final_answer
        yield ExecutorEvent(
            ExecutorEventType.METADATA,
            {
                "final_state": final_state,
                "node_latencies": node_latencies,
                "langsmith_run_url": langsmith_run_url,
            },
        )
        yield ExecutorEvent(
            ExecutorEventType.COMPLETED,
            {
                "answer": final_answer,
                "metadata": {key: value for key, value in final_state.items() if key != "answer"},
            },
        )
