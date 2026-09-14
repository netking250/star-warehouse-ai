"""Durable replay, restart reconstruction, and orphan reconciliation tests."""

import uuid
from datetime import timedelta

import pytest
from sqlmodel import select

from app.conversation.contracts import SubmitTurnCommand
from app.conversation.runtime import ConversationRuntime
from app.conversation.state_machine import RunStatus
from app.core.database import async_session_maker
from app.core.utils import utc_now
from app.models.conversation import ConversationRun
from tests.conversation.conftest import DeterministicExecutor


async def _collect(stream) -> list:
    return [event async for event in stream]


@pytest.mark.asyncio
async def test_fresh_runtime_reconstructs_final_result_and_replays_later_events(
    runtime_identity,
) -> None:
    executor = DeterministicExecutor("durable answer")
    first_runtime = ConversationRuntime(session_factory=async_session_maker, executor=executor)
    command = SubmitTurnCommand(
        conversation_id=f"conversation-{uuid.uuid4().hex}",
        question="persist this result",
        idempotency_key="reconnect-key",
    )
    submission = await first_runtime.submit_turn(identity=runtime_identity, command=command)
    await _collect(
        first_runtime.execute(
            identity=runtime_identity,
            submission=submission,
            question=command.question,
        )
    )
    first_page = await first_runtime.replay_events(
        identity=runtime_identity,
        conversation_id=command.conversation_id,
        run_id=submission.run_id,
        after_sequence=0,
    )

    fresh_executor = DeterministicExecutor("must not execute")
    fresh_runtime = ConversationRuntime(
        session_factory=async_session_maker,
        executor=fresh_executor,
    )
    recovered = await fresh_runtime.get_run(
        identity=runtime_identity,
        conversation_id=command.conversation_id,
        run_id=submission.run_id,
    )
    later_events = await fresh_runtime.replay_events(
        identity=runtime_identity,
        conversation_id=command.conversation_id,
        run_id=submission.run_id,
        after_sequence=first_page[0].sequence or 0,
    )
    duplicate = await fresh_runtime.submit_turn(identity=runtime_identity, command=command)
    duplicate_events = await _collect(
        fresh_runtime.execute(
            identity=runtime_identity,
            submission=duplicate,
            question=command.question,
        )
    )

    assert recovered.status is RunStatus.COMPLETED
    assert recovered.final_answer == "durable answer"
    assert [event.sequence for event in first_page] == [1, 2, 3]
    assert [event.sequence for event in later_events] == [2, 3]
    assert duplicate.created is False
    assert duplicate.run_id == submission.run_id
    assert duplicate_events == []
    assert fresh_executor.executions == 0


@pytest.mark.asyncio
async def test_orphaned_pending_run_is_bounded_and_failed_without_retry(
    runtime_identity,
) -> None:
    runtime = ConversationRuntime(
        session_factory=async_session_maker,
        executor=DeterministicExecutor(),
    )
    command = SubmitTurnCommand(
        conversation_id=f"conversation-{uuid.uuid4().hex}",
        question="orphan me",
        idempotency_key="orphan-key",
    )
    submission = await runtime.submit_turn(identity=runtime_identity, command=command)
    async with async_session_maker() as session, session.begin():
        run = (
            await session.exec(
                select(ConversationRun).where(
                    ConversationRun.tenant_id == runtime_identity.tenant_id,
                    ConversationRun.run_id == submission.run_id,
                )
            )
        ).one()
        run.updated_at = utc_now() - timedelta(hours=2)

    fresh_runtime = ConversationRuntime(
        session_factory=async_session_maker,
        executor=DeterministicExecutor("must not retry"),
    )
    reconciled = await fresh_runtime.reconcile_orphaned_runs(
        identity=runtime_identity,
        older_than=timedelta(hours=1),
        limit=10,
    )
    recovered = await fresh_runtime.get_run(
        identity=runtime_identity,
        conversation_id=command.conversation_id,
        run_id=submission.run_id,
    )

    assert reconciled == [submission.run_id]
    assert recovered.status is RunStatus.FAILED
    assert recovered.failure_category == "ORPHANED_RUN"
