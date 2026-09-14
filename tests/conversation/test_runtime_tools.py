"""Asynchronous tool result identity and idempotency behavior."""

import asyncio
import uuid

import pytest

from app.conversation.contracts import SubmitTurnCommand, ToolResultEnvelope
from app.conversation.runtime import ConversationRuntime, StaleRuntimeResultError
from app.conversation.state_machine import RunStatus
from app.core.database import async_session_maker
from tests.conversation.conftest import BlockingExecutor


async def _collect(stream) -> list:
    return [event async for event in stream]


async def _running_tool(runtime, identity, executor: BlockingExecutor):
    command = SubmitTurnCommand(
        conversation_id=f"conversation-{uuid.uuid4().hex}",
        question="tool",
        idempotency_key="turn-key",
    )
    submission = await runtime.submit_turn(identity=identity, command=command)
    execution = asyncio.create_task(
        _collect(
            runtime.execute(
                identity=identity,
                submission=submission,
                question=command.question,
            )
        )
    )
    await asyncio.wait_for(executor.started.wait(), timeout=2)
    tool = await runtime.request_tool(
        identity=identity,
        conversation_id=command.conversation_id,
        run_id=submission.run_id,
        tool_name="async_tool",
        idempotency_key="tool-key",
    )
    return command, submission, tool, execution


@pytest.mark.asyncio
async def test_duplicate_async_tool_result_is_applied_once(runtime_identity) -> None:
    executor = BlockingExecutor()
    runtime = ConversationRuntime(session_factory=async_session_maker, executor=executor)
    command, submission, tool, execution = await _running_tool(runtime, runtime_identity, executor)
    envelope = ToolResultEnvelope(
        tenant_id=runtime_identity.tenant_id,
        user_id=runtime_identity.user_id,
        conversation_id=command.conversation_id,
        turn_id=submission.turn_id,
        run_id=submission.run_id,
        tool_execution_id=tool.tool_execution_id,
        correlation_id=runtime_identity.correlation_id,
        delivery_id="delivery-1",
        expected_run_revision=tool.expected_run_revision,
        succeeded=True,
        result={"value": 42},
    )

    first = await runtime.accept_tool_result(identity=runtime_identity, envelope=envelope)
    duplicate = await runtime.accept_tool_result(identity=runtime_identity, envelope=envelope)
    executor.release.set()
    await asyncio.wait_for(execution, timeout=2)
    completed = await runtime.get_run(
        identity=runtime_identity,
        conversation_id=command.conversation_id,
        run_id=submission.run_id,
    )

    assert first.accepted is True
    assert duplicate.accepted is False
    assert duplicate.duplicate is True
    assert completed.status is RunStatus.COMPLETED
    assert tool.task_context.tenant_id == runtime_identity.tenant_id
    assert tool.task_context.user_id == runtime_identity.user_id
    assert tool.task_context.thread_id == command.conversation_id
    assert tool.task_context.correlation_id == runtime_identity.correlation_id


@pytest.mark.asyncio
async def test_tool_result_for_wrong_run_is_rejected(runtime_identity) -> None:
    executor = BlockingExecutor()
    runtime = ConversationRuntime(session_factory=async_session_maker, executor=executor)
    command, submission, tool, execution = await _running_tool(runtime, runtime_identity, executor)
    await runtime.cancel_run(
        identity=runtime_identity,
        conversation_id=command.conversation_id,
        run_id=submission.run_id,
    )
    other = await runtime.submit_turn(
        identity=runtime_identity,
        command=SubmitTurnCommand(
            conversation_id=command.conversation_id,
            question="other",
            idempotency_key="other-key",
        ),
    )

    with pytest.raises(StaleRuntimeResultError):
        await runtime.accept_tool_result(
            identity=runtime_identity,
            envelope=ToolResultEnvelope(
                tenant_id=runtime_identity.tenant_id,
                user_id=runtime_identity.user_id,
                conversation_id=command.conversation_id,
                turn_id=other.turn_id,
                run_id=other.run_id,
                tool_execution_id=tool.tool_execution_id,
                correlation_id=runtime_identity.correlation_id,
                delivery_id="wrong-run",
                expected_run_revision=tool.expected_run_revision,
                succeeded=True,
            ),
        )
    executor.release.set()
    await asyncio.wait_for(execution, timeout=2)


@pytest.mark.asyncio
async def test_tool_failure_durably_fails_run(runtime_identity) -> None:
    executor = BlockingExecutor()
    runtime = ConversationRuntime(session_factory=async_session_maker, executor=executor)
    command, submission, tool, execution = await _running_tool(runtime, runtime_identity, executor)
    accepted = await runtime.accept_tool_result(
        identity=runtime_identity,
        envelope=ToolResultEnvelope(
            tenant_id=runtime_identity.tenant_id,
            user_id=runtime_identity.user_id,
            conversation_id=command.conversation_id,
            turn_id=submission.turn_id,
            run_id=submission.run_id,
            tool_execution_id=tool.tool_execution_id,
            correlation_id=runtime_identity.correlation_id,
            delivery_id="tool-failed",
            expected_run_revision=tool.expected_run_revision,
            succeeded=False,
            failure_category="DEPENDENCY_ERROR",
        ),
    )
    duplicate = await runtime.accept_tool_result(
        identity=runtime_identity,
        envelope=ToolResultEnvelope(
            tenant_id=runtime_identity.tenant_id,
            user_id=runtime_identity.user_id,
            conversation_id=command.conversation_id,
            turn_id=submission.turn_id,
            run_id=submission.run_id,
            tool_execution_id=tool.tool_execution_id,
            correlation_id=runtime_identity.correlation_id,
            delivery_id="tool-failed",
            expected_run_revision=tool.expected_run_revision,
            succeeded=False,
            failure_category="DEPENDENCY_ERROR",
        ),
    )
    executor.release.set()
    await asyncio.wait_for(execution, timeout=2)

    assert accepted.run.status is RunStatus.FAILED
    assert accepted.run.failure_category == "DEPENDENCY_ERROR"
    assert duplicate.duplicate is True
