"""Regression tests for durable conversation-history hydration."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from langchain_core.runnables import RunnableConfig

from app.conversation.contracts import (
    ExecutionRequest,
    ExecutorEvent,
    ExecutorEventType,
    SubmitTurnCommand,
)
from app.conversation.langgraph_executor import LangGraphConversationExecutor
from app.conversation.runtime import ConversationRuntime
from app.core.database import async_session_maker
from app.models.state import AgentState
from tests.conversation.conftest import DeterministicExecutor


async def _collect(stream: AsyncIterator[Any]) -> list[Any]:
    return [event async for event in stream]


class _RecordingExecutor(DeterministicExecutor):
    """Capture execution requests while retaining deterministic completion."""

    def __init__(self) -> None:
        super().__init__()
        self.requests: list[ExecutionRequest] = []

    async def execute(self, request: ExecutionRequest) -> AsyncIterator[ExecutorEvent]:
        self.requests.append(request)
        async for event in super().execute(request):
            yield event


@pytest.mark.asyncio
async def test_runtime_hydrates_completed_turn_pairs_for_next_execution(runtime_identity) -> None:
    executor = _RecordingExecutor()
    runtime = ConversationRuntime(session_factory=async_session_maker, executor=executor)
    conversation_id = f"history-{uuid.uuid4().hex}"

    first_command = SubmitTurnCommand(
        conversation_id=conversation_id,
        question="Aurora Chair return window?",
        idempotency_key="history-first",
    )
    first = await runtime.submit_turn(identity=runtime_identity, command=first_command)
    await _collect(
        runtime.execute(
            identity=runtime_identity,
            submission=first,
            question=first_command.question,
        )
    )

    second_command = SubmitTurnCommand(
        conversation_id=conversation_id,
        question="I bought it ten days ago.",
        idempotency_key="history-second",
    )
    second = await runtime.submit_turn(identity=runtime_identity, command=second_command)

    assert list(second.history) == [
        {"role": "user", "content": "Aurora Chair return window?"},
        {"role": "assistant", "content": "deterministic answer"},
    ]

    await _collect(
        runtime.execute(
            identity=runtime_identity,
            submission=second,
            question=second_command.question,
        )
    )
    assert list(executor.requests[1].history) == list(second.history)


@pytest.mark.asyncio
async def test_runtime_history_is_scoped_to_conversation(runtime_identity) -> None:
    executor = _RecordingExecutor()
    runtime = ConversationRuntime(session_factory=async_session_maker, executor=executor)

    first_conversation = f"history-owner-a-{uuid.uuid4().hex}"
    first_command = SubmitTurnCommand(
        conversation_id=first_conversation,
        question="Aurora Chair return window?",
        idempotency_key="history-owner-a-first",
    )
    first = await runtime.submit_turn(identity=runtime_identity, command=first_command)
    await _collect(
        runtime.execute(
            identity=runtime_identity,
            submission=first,
            question=first_command.question,
        )
    )

    second_conversation = f"history-owner-b-{uuid.uuid4().hex}"
    second = await runtime.submit_turn(
        identity=runtime_identity,
        command=SubmitTurnCommand(
            conversation_id=second_conversation,
            question="I bought it ten days ago.",
            idempotency_key="history-owner-b-first",
        ),
    )

    assert second.history == ()


@pytest.mark.asyncio
async def test_runtime_excludes_failed_turns_and_idempotent_replays_from_history(
    runtime_identity,
) -> None:
    failing_runtime = ConversationRuntime(
        session_factory=async_session_maker,
        executor=_FailingExecutor(),
    )
    conversation_id = f"history-failure-{uuid.uuid4().hex}"
    failed_command = SubmitTurnCommand(
        conversation_id=conversation_id,
        question="failed partial question",
        idempotency_key="history-failed",
    )
    failed = await failing_runtime.submit_turn(
        identity=runtime_identity,
        command=failed_command,
    )
    with pytest.raises(RuntimeError, match="history failure"):
        await _collect(
            failing_runtime.execute(
                identity=runtime_identity,
                submission=failed,
                question=failed_command.question,
            )
        )

    executor = _RecordingExecutor()
    runtime = ConversationRuntime(session_factory=async_session_maker, executor=executor)
    next_command = SubmitTurnCommand(
        conversation_id=conversation_id,
        question="new question",
        idempotency_key="history-after-failure",
    )
    next_submission = await runtime.submit_turn(
        identity=runtime_identity,
        command=next_command,
    )
    assert list(next_submission.history) == []

    await _collect(
        runtime.execute(
            identity=runtime_identity,
            submission=next_submission,
            question=next_command.question,
        )
    )
    replay = await runtime.submit_turn(identity=runtime_identity, command=next_command)
    assert replay.created is False
    assert replay.turn_id == next_submission.turn_id
    assert replay.history == ()
    assert len(executor.requests) == 1


class _FailingExecutor:
    """Raise a deterministic failure without persisting an assistant answer."""

    async def execute(self, request: ExecutionRequest) -> AsyncIterator[ExecutorEvent]:
        raise RuntimeError("history failure")
        yield ExecutorEvent(ExecutorEventType.COMPLETED, {"answer": request.question})


class _CapturingGraph:
    """Capture the initial state passed into the LangGraph adapter."""

    def __init__(self, expected_run_id: str = "run-1") -> None:
        self.initial_state: AgentState | None = None
        self.config: RunnableConfig | None = None
        self.expected_run_id = expected_run_id

    async def astream_events(
        self,
        input: AgentState,
        config: RunnableConfig,
        *,
        version: str,
    ) -> AsyncIterator[dict[str, Any]]:
        self.initial_state = input
        self.config = config
        assert config["configurable"]["checkpoint_ns"].endswith(f":{self.expected_run_id}")
        assert version == "v2"
        yield {
            "event": "on_chain_end",
            "metadata": {"langgraph_node": "synthesis_node"},
            "run_id": "graph-run",
            "data": {"output": {"answer": "ok"}},
        }


@pytest.mark.asyncio
async def test_langgraph_executor_appends_current_message_once_and_preserves_history() -> None:
    graph = _CapturingGraph()
    executor = LangGraphConversationExecutor(graph)
    request = ExecutionRequest(
        tenant_id="tenant-a",
        user_id=7,
        conversation_id="conversation-1",
        turn_id="turn-1",
        run_id="run-1",
        correlation_id="correlation-1",
        trace_id=None,
        question="current question",
        history=(
            {"role": "user", "content": "previous question"},
            {"role": "assistant", "content": "previous answer"},
        ),
    )

    events = [event async for event in executor.execute(request)]

    assert graph.initial_state is not None
    assert graph.initial_state["history"] == [
        {"role": "user", "content": "previous question"},
        {"role": "assistant", "content": "previous answer"},
        {"role": "user", "content": "current question"},
    ]
    assert (
        sum(
            message == {"role": "user", "content": "current question"}
            for message in graph.initial_state["history"]
        )
        == 1
    )
    assert str(events[-1].event_type) == "COMPLETED"
    assert events[-1].payload["answer"] == "ok"


@pytest.mark.asyncio
async def test_langgraph_executor_uses_run_specific_checkpoint_thread_identity() -> None:
    first_graph = _CapturingGraph()
    second_graph = _CapturingGraph("run-2")

    await _collect(
        LangGraphConversationExecutor(first_graph).execute(
            ExecutionRequest(
                tenant_id="tenant-a",
                user_id=7,
                conversation_id="conversation-1",
                turn_id="turn-1",
                run_id="run-1",
                correlation_id="correlation-1",
                trace_id=None,
                question="current question",
            )
        )
    )
    await _collect(
        LangGraphConversationExecutor(second_graph).execute(
            ExecutionRequest(
                tenant_id="tenant-a",
                user_id=7,
                conversation_id="conversation-1",
                turn_id="turn-2",
                run_id="run-2",
                correlation_id="correlation-1",
                trace_id=None,
                question="current question",
            )
        )
    )

    assert first_graph.config is not None
    assert second_graph.config is not None
    assert (
        first_graph.config["configurable"]["thread_id"]
        != second_graph.config["configurable"]["thread_id"]
    )
    assert first_graph.initial_state is not None
    assert second_graph.initial_state is not None
    assert first_graph.initial_state["thread_id"] == "conversation-1"
    assert second_graph.initial_state["thread_id"] == "conversation-1"
