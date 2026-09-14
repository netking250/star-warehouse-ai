"""Verify the T13 mock gateway through the durable T12 conversation runtime."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import cast

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import func, select

from app.conversation.contracts import ConversationIdentity, SubmitTurnCommand
from app.conversation.langgraph_executor import (
    LangGraphConversationExecutor,
    LangGraphEventSource,
)
from app.conversation.runtime import ConversationRuntime
from app.conversation.state_machine import RunStatus
from app.core.config import settings
from app.core.database import async_session_maker
from app.core.rls import MAINTENANCE_CAPABILITY_ROLE, RUNTIME_CAPABILITY_ROLE
from app.core.tenancy import TenantStatus, tenant_scope
from app.model_gateway.contracts import (
    ModelCandidate,
    ModelRequest,
    ModelRoute,
    ModelStreamEvent,
)
from app.model_gateway.gateway import ModelGateway
from app.model_gateway.langchain import GatewayChatModel
from app.model_gateway.providers.mock import MockProviderAdapter
from app.models.message import MessageCard
from app.models.state import AgentState
from app.models.user import User


class _BlockingMockProviderAdapter(MockProviderAdapter):
    """Hold one deterministic provider completion until cancellation is durable."""

    def __init__(self) -> None:
        super().__init__(stream_chunks=("late ", "answer"))
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def stream(
        self, candidate: ModelCandidate, request: ModelRequest
    ) -> AsyncIterator[ModelStreamEvent]:
        self.started.set()
        await self.release.wait()
        async for event in super().stream(candidate, request):
            yield event


async def _prepare_identity() -> ConversationIdentity:
    """Prepare one isolated tenant user using only the dedicated test database."""
    if not settings.POSTGRES_DB.startswith("test_"):
        raise RuntimeError("T13 runtime smoke requires a test_ PostgreSQL database")
    setup_engine = create_async_engine(settings.MIGRATION_DATABASE_URL)
    try:
        async with setup_engine.begin() as connection:
            await connection.execute(
                text(
                    "GRANT USAGE ON SCHEMA public TO "
                    f"{RUNTIME_CAPABILITY_ROLE}, {MAINTENANCE_CAPABILITY_ROLE}"
                )
            )
            await connection.execute(
                text(
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "
                    f"{RUNTIME_CAPABILITY_ROLE}, {MAINTENANCE_CAPABILITY_ROLE}"
                )
            )
            await connection.execute(
                text(
                    "GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO "
                    f"{RUNTIME_CAPABILITY_ROLE}, {MAINTENANCE_CAPABILITY_ROLE}"
                )
            )
            await connection.execute(
                text(
                    "INSERT INTO tenants (id, slug, display_name, status) "
                    "VALUES (:tenant_id, :tenant_id, 'T13 Smoke Tenant', :status) "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                {
                    "tenant_id": settings.LOCAL_BOOTSTRAP_TENANT_ID,
                    "status": TenantStatus.ACTIVE,
                },
            )
    finally:
        await setup_engine.dispose()

    suffix = uuid.uuid4().hex[:10]
    with tenant_scope(settings.LOCAL_BOOTSTRAP_TENANT_ID):
        async with async_session_maker() as session:
            user = User(
                username=f"t13_smoke_{suffix}",
                password_hash=User.hash_password("password123"),
                email=f"t13_smoke_{suffix}@example.test",
                full_name="T13 Smoke",
                is_active=True,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            if user.id is None:
                raise AssertionError("T13 smoke user was not persisted")
            return ConversationIdentity(
                tenant_id=settings.LOCAL_BOOTSTRAP_TENANT_ID,
                user_id=user.id,
                correlation_id=f"t13-smoke-{suffix}",
                trace_id=None,
            )


def _build_runtime(adapter: MockProviderAdapter) -> ConversationRuntime:
    """Build the real T12 executor around one provider-neutral mock adapter."""
    candidate = ModelCandidate(
        provider="mock",
        model="mock-runtime-v1",
        capabilities=adapter.capabilities,
        timeout_seconds=1.0,
    )
    gateway = ModelGateway(
        adapters=[adapter],
        routes=[ModelRoute(name="default_chat", candidates=(candidate,))],
    )
    model = GatewayChatModel(gateway=gateway, route="default_chat")

    async def synthesis_node(state: AgentState) -> dict[str, object]:
        chunks: list[str] = []
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
    return ConversationRuntime(
        session_factory=async_session_maker,
        executor=LangGraphConversationExecutor(cast(LangGraphEventSource, builder.compile())),
    )


async def verify_runtime_flow() -> None:
    """Execute and validate tenant-scoped completion and cancellation flows."""
    adapter = MockProviderAdapter(stream_chunks=("deterministic ", "answer"))
    runtime = _build_runtime(adapter)
    identity = await _prepare_identity()
    command = SubmitTurnCommand(
        conversation_id=f"gateway-runtime-{uuid.uuid4().hex}",
        question="hello",
        idempotency_key="gateway-runtime-flow",
    )
    with tenant_scope(identity.tenant_id):
        submission = await runtime.submit_turn(identity=identity, command=command)
        events = [
            event
            async for event in runtime.execute(
                identity=identity,
                submission=submission,
                question=command.question,
            )
        ]
        snapshot = await runtime.get_run(
            identity=identity,
            conversation_id=command.conversation_id,
            run_id=submission.run_id,
        )
        async with async_session_maker() as session:
            messages = (
                await session.exec(
                    select(MessageCard).where(
                        MessageCard.tenant_id == identity.tenant_id,
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
                        MessageCard.tenant_id == identity.tenant_id,
                        MessageCard.logical_message_id == f"assistant:{submission.turn_id}",
                    )
                )
            ).one()

    assert snapshot.status is RunStatus.COMPLETED
    assert snapshot.final_answer == "deterministic answer"
    assert assistant_count == 1
    assert len(messages) == 1
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
    assert adapter.attempt_count == 1

    blocking_adapter = _BlockingMockProviderAdapter()
    cancellation_runtime = _build_runtime(blocking_adapter)
    cancellation_command = SubmitTurnCommand(
        conversation_id=f"gateway-cancel-{uuid.uuid4().hex}",
        question="cancel this model run",
        idempotency_key="gateway-cancellation-flow",
    )
    with tenant_scope(identity.tenant_id):
        cancellation_submission = await cancellation_runtime.submit_turn(
            identity=identity,
            command=cancellation_command,
        )

        async def collect_late_events() -> list[object]:
            return [
                event
                async for event in cancellation_runtime.execute(
                    identity=identity,
                    submission=cancellation_submission,
                    question=cancellation_command.question,
                )
            ]

        execution = asyncio.create_task(collect_late_events())
        await asyncio.wait_for(blocking_adapter.started.wait(), timeout=2)
        first_cancel = await cancellation_runtime.cancel_run(
            identity=identity,
            conversation_id=cancellation_command.conversation_id,
            run_id=cancellation_submission.run_id,
        )
        second_cancel = await cancellation_runtime.cancel_run(
            identity=identity,
            conversation_id=cancellation_command.conversation_id,
            run_id=cancellation_submission.run_id,
        )
        blocking_adapter.release.set()
        await asyncio.wait_for(execution, timeout=2)
        cancelled_snapshot = await cancellation_runtime.get_run(
            identity=identity,
            conversation_id=cancellation_command.conversation_id,
            run_id=cancellation_submission.run_id,
        )
        async with async_session_maker() as session:
            late_assistant_count = (
                await session.exec(
                    select(func.count())
                    .select_from(MessageCard)
                    .where(
                        MessageCard.tenant_id == identity.tenant_id,
                        MessageCard.run_id == cancellation_submission.run_id,
                        MessageCard.sender_type == "agent",
                    )
                )
            ).one()

    assert first_cancel.outcome == "CANCELLED"
    assert second_cancel.outcome == "ALREADY_CANCELLED"
    assert cancelled_snapshot.status is RunStatus.CANCELLED
    assert cancelled_snapshot.final_answer is None
    assert late_assistant_count == 0
    assert blocking_adapter.attempt_count == 1


if __name__ == "__main__":
    asyncio.run(verify_runtime_flow())
    print("T13 runtime smoke: PASS")
