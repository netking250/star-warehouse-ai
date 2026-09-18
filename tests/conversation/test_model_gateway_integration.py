"""T13 deterministic model flow through the durable T12 runtime."""

import uuid
from typing import cast

import pytest
from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph
from sqlmodel import func, select

from app.conversation.contracts import SubmitTurnCommand
from app.conversation.langgraph_executor import (
    LangGraphConversationExecutor,
    LangGraphEventSource,
)
from app.conversation.runtime import ConversationRuntime
from app.conversation.state_machine import RunStatus
from app.core.database import async_session_maker
from app.memory.summarizer import SessionSummarizer
from app.model_gateway.contracts import ModelCandidate, ModelCapability, ModelRoute
from app.model_gateway.gateway import ModelGateway
from app.model_gateway.langchain import GatewayChatModel
from app.model_gateway.providers.mock import MockProviderAdapter
from app.models.message import MessageCard
from app.models.state import AgentState


@pytest.mark.asyncio
async def test_authenticated_runtime_flow_persists_one_mock_gateway_result(
    runtime_identity,
) -> None:
    adapter = MockProviderAdapter(
        content="internal Aurora summary",
        stream_chunks=("Aurora refund window is ", "17 days."),
    )
    candidate = ModelCandidate(
        provider="mock",
        model="mock-runtime-v1",
        capabilities=adapter.capabilities,
        timeout_seconds=1.0,
    )
    summarization_candidate = ModelCandidate(
        provider="mock",
        model="mock-summarization-chat-only",
        capabilities=frozenset({ModelCapability.CHAT}),
        timeout_seconds=1.0,
    )
    gateway = ModelGateway(
        adapters=[adapter],
        routes=[
            ModelRoute(name="default_chat", candidates=(candidate,)),
            ModelRoute(name="summarization", candidates=(summarization_candidate,)),
        ],
    )
    model = GatewayChatModel(gateway=gateway, route="default_chat")
    summarizer = SessionSummarizer(GatewayChatModel(gateway=gateway, route="summarization"))
    summaries: list[str] = []

    async def synthesis_node(state: AgentState) -> dict[str, object]:
        summaries.append(
            await summarizer.summarize_thread(
                [
                    {
                        "role": "system",
                        "content": "Document A evidence: AURORA-REFUND-17",
                    },
                    {"role": "user", "content": state["question"]},
                ]
            )
        )
        chunks = []
        provider: str | None = None
        actual_model: str | None = None
        async for chunk in model.astream(
            [HumanMessage(content=state["question"])],
            config={"tags": ["user_visible"]},
        ):
            chunks.append(str(chunk.content))
            provider = str(chunk.response_metadata.get("provider") or provider or "") or None
            actual_model = str(chunk.response_metadata.get("model") or actual_model or "") or None
        return {
            "answer": "".join(chunks),
            "model_provider": provider,
            "model_name": actual_model,
        }

    # LangGraph 1.0.10's bound does not recognize typing_extensions-compatible TypedDicts.
    builder = StateGraph(AgentState)  # ty: ignore[invalid-argument-type]
    builder.add_node("synthesis_node", synthesis_node)
    builder.add_edge(START, "synthesis_node")
    builder.add_edge("synthesis_node", END)
    graph = cast(LangGraphEventSource, builder.compile())
    runtime = ConversationRuntime(
        session_factory=async_session_maker,
        executor=LangGraphConversationExecutor(graph),
    )
    command = SubmitTurnCommand(
        conversation_id=f"gateway-runtime-{uuid.uuid4().hex}",
        question="What is the refund window for the Aurora Chair?",
        idempotency_key="gateway-runtime-flow",
    )
    submission = await runtime.submit_turn(identity=runtime_identity, command=command)

    events = [
        event
        async for event in runtime.execute(
            identity=runtime_identity,
            submission=submission,
            question=command.question,
        )
    ]
    snapshot = await runtime.get_run(
        identity=runtime_identity,
        conversation_id=command.conversation_id,
        run_id=submission.run_id,
    )
    async with async_session_maker() as session:
        messages = (
            await session.exec(
                select(MessageCard).where(
                    MessageCard.tenant_id == runtime_identity.tenant_id,
                    MessageCard.run_id == submission.run_id,
                    MessageCard.sender_type == "agent",
                )
            )
        ).all()
        assistant_count = (
            await session.exec(
                select(func.count())
                .select_from(MessageCard)
                .where(
                    MessageCard.tenant_id == runtime_identity.tenant_id,
                    MessageCard.logical_message_id == f"assistant:{submission.turn_id}",
                )
            )
        ).one()

    assert snapshot.status is RunStatus.COMPLETED
    assert snapshot.final_answer == "Aurora refund window is 17 days."
    assert assistant_count == 1
    assert len(messages) == 1
    assert summaries == ["internal Aurora summary"]
    metadata = messages[0].meta_data
    assert metadata is not None
    assert metadata["model_provider"] == "mock"
    assert metadata["model_name"] == "mock-runtime-v1"
    event_types = [str(event.event_type) for event in events]
    assert event_types == [
        "RUN_STARTED",
        "TOKEN",
        "TOKEN",
        "METADATA",
        "RUN_COMPLETED",
    ], event_types
    assert event_types.count("RUN_COMPLETED") == 1
    assert "RUN_FAILED" not in event_types
    assert adapter.attempt_count == 2
