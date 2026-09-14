"""Idempotent submission and terminal-result behavior through the runtime interface."""

import uuid

import pytest
from sqlmodel import func, select

from app.conversation.contracts import SubmitTurnCommand
from app.conversation.runtime import ConversationRuntime, IdempotencyConflictError
from app.conversation.state_machine import RunStatus
from app.core.database import async_session_maker
from app.models.message import MessageCard
from tests.conversation.conftest import DeterministicExecutor, FailingExecutor


async def _collect(stream) -> list:
    return [event async for event in stream]


@pytest.mark.asyncio
async def test_duplicate_submission_returns_one_turn_run_and_terminal_response(
    runtime_identity,
) -> None:
    executor = DeterministicExecutor()
    runtime = ConversationRuntime(session_factory=async_session_maker, executor=executor)
    command = SubmitTurnCommand(
        conversation_id=f"conversation-{uuid.uuid4().hex}",
        question="Where is my order?",
        idempotency_key="browser-retry-1",
    )

    first = await runtime.submit_turn(identity=runtime_identity, command=command)
    first_events = await _collect(
        runtime.execute(
            identity=runtime_identity,
            submission=first,
            question=command.question,
        )
    )
    duplicate = await runtime.submit_turn(identity=runtime_identity, command=command)
    duplicate_events = await _collect(
        runtime.execute(
            identity=runtime_identity,
            submission=duplicate,
            question=command.question,
        )
    )
    recovered = await runtime.get_run(
        identity=runtime_identity,
        conversation_id=command.conversation_id,
        run_id=first.run_id,
    )
    terminal_cancel = await runtime.cancel_run(
        identity=runtime_identity,
        conversation_id=command.conversation_id,
        run_id=first.run_id,
    )
    async with async_session_maker() as session:
        assistant_count = (
            await session.exec(
                select(func.count())
                .select_from(MessageCard)
                .where(
                    MessageCard.tenant_id == runtime_identity.tenant_id,
                    MessageCard.logical_message_id == f"assistant:{first.turn_id}",
                )
            )
        ).one()

    assert first.created is True
    assert duplicate.created is False
    assert duplicate.turn_id == first.turn_id
    assert duplicate.run_id == first.run_id
    assert executor.executions == 1
    assert duplicate_events == []
    assert recovered.status is RunStatus.COMPLETED
    assert recovered.final_answer == "deterministic answer"
    assert terminal_cancel.outcome == "TERMINAL_UNCHANGED"
    assert terminal_cancel.run.status is RunStatus.COMPLETED
    assert assistant_count == 1
    assert [str(event.event_type) for event in first_events] == [
        "RUN_STARTED",
        "TOKEN",
        "RUN_COMPLETED",
    ]


@pytest.mark.asyncio
async def test_same_idempotency_key_in_different_conversations_is_isolated(
    runtime_identity,
) -> None:
    executor = DeterministicExecutor()
    runtime = ConversationRuntime(session_factory=async_session_maker, executor=executor)
    first = await runtime.submit_turn(
        identity=runtime_identity,
        command=SubmitTurnCommand(
            conversation_id=f"conversation-{uuid.uuid4().hex}",
            question="first",
            idempotency_key="shared-key",
        ),
    )
    second = await runtime.submit_turn(
        identity=runtime_identity,
        command=SubmitTurnCommand(
            conversation_id=f"conversation-{uuid.uuid4().hex}",
            question="second",
            idempotency_key="shared-key",
        ),
    )

    assert first.turn_id != second.turn_id
    assert first.run_id != second.run_id


@pytest.mark.asyncio
async def test_same_key_with_different_message_is_rejected(runtime_identity) -> None:
    runtime = ConversationRuntime(
        session_factory=async_session_maker,
        executor=DeterministicExecutor(),
    )
    conversation_id = f"conversation-{uuid.uuid4().hex}"
    await runtime.submit_turn(
        identity=runtime_identity,
        command=SubmitTurnCommand(
            conversation_id=conversation_id,
            question="original",
            idempotency_key="reused-key",
        ),
    )

    with pytest.raises(IdempotencyConflictError):
        await runtime.submit_turn(
            identity=runtime_identity,
            command=SubmitTurnCommand(
                conversation_id=conversation_id,
                question="different",
                idempotency_key="reused-key",
            ),
        )


@pytest.mark.asyncio
async def test_executor_failure_produces_durable_failed_state(runtime_identity) -> None:
    runtime = ConversationRuntime(
        session_factory=async_session_maker,
        executor=FailingExecutor(),
    )
    command = SubmitTurnCommand(
        conversation_id=f"conversation-{uuid.uuid4().hex}",
        question="fail deterministically",
        idempotency_key="failure-key",
    )
    submission = await runtime.submit_turn(identity=runtime_identity, command=command)

    with pytest.raises(RuntimeError, match="deterministic executor failure"):
        await _collect(
            runtime.execute(
                identity=runtime_identity,
                submission=submission,
                question=command.question,
            )
        )
    snapshot = await runtime.get_run(
        identity=runtime_identity,
        conversation_id=command.conversation_id,
        run_id=submission.run_id,
    )
    events = await runtime.replay_events(
        identity=runtime_identity,
        conversation_id=command.conversation_id,
        run_id=submission.run_id,
    )

    assert snapshot.status is RunStatus.FAILED
    assert snapshot.failure_category == "EXECUTOR_ERROR"
    assert str(events[-1].event_type) == "RUN_FAILED"
