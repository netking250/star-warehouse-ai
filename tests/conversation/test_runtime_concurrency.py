"""Actual async concurrency and cancellation behavior for conversation runs."""

import asyncio
import uuid

import pytest

from app.conversation.contracts import SubmitTurnCommand, ToolResultEnvelope
from app.conversation.runtime import ConversationBusyError, ConversationRuntime
from app.conversation.state_machine import RunStatus
from app.core.database import async_session_maker
from tests.conversation.conftest import BlockingExecutor, ConcurrentExecutor


async def _collect(stream) -> list:
    return [event async for event in stream]


@pytest.mark.asyncio
async def test_two_concurrent_messages_for_same_conversation_accept_exactly_one(
    runtime_identity,
) -> None:
    runtime = ConversationRuntime(
        session_factory=async_session_maker,
        executor=BlockingExecutor(),
    )
    conversation_id = f"conversation-{uuid.uuid4().hex}"
    results = await asyncio.gather(
        runtime.submit_turn(
            identity=runtime_identity,
            command=SubmitTurnCommand(
                conversation_id=conversation_id,
                question="first",
                idempotency_key="first-key",
            ),
        ),
        runtime.submit_turn(
            identity=runtime_identity,
            command=SubmitTurnCommand(
                conversation_id=conversation_id,
                question="second",
                idempotency_key="second-key",
            ),
        ),
        return_exceptions=True,
    )

    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert sum(isinstance(result, ConversationBusyError) for result in results) == 1


@pytest.mark.asyncio
async def test_different_conversations_execute_concurrently(runtime_identity) -> None:
    executor = ConcurrentExecutor()
    runtime = ConversationRuntime(session_factory=async_session_maker, executor=executor)
    submissions = []
    for suffix in ("a", "b"):
        command = SubmitTurnCommand(
            conversation_id=f"conversation-{suffix}-{uuid.uuid4().hex}",
            question=suffix,
            idempotency_key=f"key-{suffix}",
        )
        submissions.append(
            (command, await runtime.submit_turn(identity=runtime_identity, command=command))
        )

    await asyncio.gather(
        *[
            _collect(
                runtime.execute(
                    identity=runtime_identity,
                    submission=submission,
                    question=command.question,
                )
            )
            for command, submission in submissions
        ]
    )

    assert executor.started_count == 2
    for command, submission in submissions:
        snapshot = await runtime.get_run(
            identity=runtime_identity,
            conversation_id=command.conversation_id,
            run_id=submission.run_id,
        )
        assert snapshot.status is RunStatus.COMPLETED


@pytest.mark.asyncio
async def test_cancel_racing_with_completion_remains_terminal_cancelled(
    runtime_identity,
) -> None:
    executor = BlockingExecutor()
    runtime = ConversationRuntime(session_factory=async_session_maker, executor=executor)
    command = SubmitTurnCommand(
        conversation_id=f"conversation-{uuid.uuid4().hex}",
        question="cancel me",
        idempotency_key="cancel-key",
    )
    submission = await runtime.submit_turn(identity=runtime_identity, command=command)
    execution = asyncio.create_task(
        _collect(
            runtime.execute(
                identity=runtime_identity,
                submission=submission,
                question=command.question,
            )
        )
    )
    await asyncio.wait_for(executor.started.wait(), timeout=2)

    first_cancel = await runtime.cancel_run(
        identity=runtime_identity,
        conversation_id=command.conversation_id,
        run_id=submission.run_id,
    )
    second_cancel = await runtime.cancel_run(
        identity=runtime_identity,
        conversation_id=command.conversation_id,
        run_id=submission.run_id,
    )
    executor.release.set()
    await asyncio.wait_for(execution, timeout=2)
    snapshot = await runtime.get_run(
        identity=runtime_identity,
        conversation_id=command.conversation_id,
        run_id=submission.run_id,
    )

    assert first_cancel.outcome == "CANCELLED"
    assert second_cancel.outcome == "ALREADY_CANCELLED"
    assert snapshot.status is RunStatus.CANCELLED
    assert snapshot.final_answer is None


@pytest.mark.asyncio
async def test_stale_run_a_tool_result_cannot_mutate_current_run_b(runtime_identity) -> None:
    executor = BlockingExecutor()
    runtime = ConversationRuntime(session_factory=async_session_maker, executor=executor)
    conversation_id = f"conversation-{uuid.uuid4().hex}"
    command_a = SubmitTurnCommand(
        conversation_id=conversation_id,
        question="run a",
        idempotency_key="run-a",
    )
    run_a = await runtime.submit_turn(identity=runtime_identity, command=command_a)
    execution_a = asyncio.create_task(
        _collect(
            runtime.execute(
                identity=runtime_identity,
                submission=run_a,
                question=command_a.question,
            )
        )
    )
    await asyncio.wait_for(executor.started.wait(), timeout=2)
    tool = await runtime.request_tool(
        identity=runtime_identity,
        conversation_id=conversation_id,
        run_id=run_a.run_id,
        tool_name="slow_tool",
        idempotency_key="tool-a",
    )
    await runtime.cancel_run(
        identity=runtime_identity,
        conversation_id=conversation_id,
        run_id=run_a.run_id,
    )
    run_b = await runtime.submit_turn(
        identity=runtime_identity,
        command=SubmitTurnCommand(
            conversation_id=conversation_id,
            question="run b",
            idempotency_key="run-b",
        ),
    )

    accepted = await runtime.accept_tool_result(
        identity=runtime_identity,
        envelope=ToolResultEnvelope(
            tenant_id=runtime_identity.tenant_id,
            user_id=runtime_identity.user_id,
            conversation_id=conversation_id,
            turn_id=run_a.turn_id,
            run_id=run_a.run_id,
            tool_execution_id=tool.tool_execution_id,
            correlation_id=runtime_identity.correlation_id,
            delivery_id="late-delivery",
            expected_run_revision=tool.expected_run_revision,
            succeeded=True,
            result={"value": "late"},
        ),
    )
    executor.release.set()
    await asyncio.wait_for(execution_a, timeout=2)
    current = await runtime.get_run(
        identity=runtime_identity,
        conversation_id=conversation_id,
        run_id=run_b.run_id,
    )

    assert accepted.accepted is False
    assert accepted.reason == "STALE_RUN"
    assert current.status is RunStatus.PENDING
    assert current.final_answer is None
