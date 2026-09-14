"""Atomic persistence tests for turn acceptance and terminal completion."""

import uuid

import pytest
from sqlalchemy import text
from sqlmodel import func, select

from app.conversation.contracts import SubmitTurnCommand
from app.conversation.runtime import ConversationRuntime
from app.conversation.state_machine import RunStatus
from app.core.database import async_session_maker
from app.models.conversation import Conversation, ConversationRun, ConversationTurn
from app.models.message import MessageCard
from tests.conversation.conftest import DeterministicExecutor


async def _install_event_failure_trigger(engine, event_type: str) -> None:
    assert event_type in {"TURN_ACCEPTED", "RUN_COMPLETED"}
    async with engine.begin() as connection:
        await connection.execute(
            text(
                """
                CREATE OR REPLACE FUNCTION t12_reject_runtime_event() RETURNS trigger AS $$
                BEGIN
                    IF NEW.event_type = TG_ARGV[0] THEN
                        RAISE EXCEPTION 'forced T12 atomicity failure';
                    END IF;
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
                """
            )
        )
        await connection.execute(
            text(
                "DROP TRIGGER IF EXISTS t12_reject_runtime_event_trigger "
                "ON conversation_runtime_events"
            )
        )
        await connection.execute(
            text(
                "CREATE TRIGGER t12_reject_runtime_event_trigger "
                "BEFORE INSERT ON conversation_runtime_events "
                "FOR EACH ROW EXECUTE FUNCTION t12_reject_runtime_event"
                f"('{event_type}')"
            )
        )


async def _remove_event_failure_trigger(engine) -> None:
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "DROP TRIGGER IF EXISTS t12_reject_runtime_event_trigger "
                "ON conversation_runtime_events"
            )
        )
        await connection.execute(text("DROP FUNCTION IF EXISTS t12_reject_runtime_event()"))


@pytest.mark.asyncio
async def test_turn_acceptance_failure_rolls_back_all_runtime_records(
    runtime_identity,
    test_maintenance_engine,
) -> None:
    runtime = ConversationRuntime(
        session_factory=async_session_maker,
        executor=DeterministicExecutor(),
    )
    conversation_id = f"conversation-{uuid.uuid4().hex}"
    await _install_event_failure_trigger(test_maintenance_engine, "TURN_ACCEPTED")
    try:
        with pytest.raises(Exception, match="forced T12 atomicity failure"):
            await runtime.submit_turn(
                identity=runtime_identity,
                command=SubmitTurnCommand(
                    conversation_id=conversation_id,
                    question="fail atomically",
                    idempotency_key="atomic-turn",
                ),
            )
    finally:
        await _remove_event_failure_trigger(test_maintenance_engine)

    async with async_session_maker() as session:
        conversations = await session.exec(
            select(func.count())
            .select_from(Conversation)
            .where(Conversation.conversation_id == conversation_id)
        )
        turns = await session.exec(
            select(func.count())
            .select_from(ConversationTurn)
            .where(ConversationTurn.conversation_id == conversation_id)
        )
        runs = await session.exec(
            select(func.count())
            .select_from(ConversationRun)
            .where(ConversationRun.conversation_id == conversation_id)
        )
        messages = await session.exec(
            select(func.count())
            .select_from(MessageCard)
            .where(MessageCard.conversation_id == conversation_id)
        )

    assert conversations.one() == 0
    assert turns.one() == 0
    assert runs.one() == 0
    assert messages.one() == 0


@pytest.mark.asyncio
async def test_completion_failure_never_leaves_completed_run_without_message(
    runtime_identity,
    test_maintenance_engine,
) -> None:
    runtime = ConversationRuntime(
        session_factory=async_session_maker,
        executor=DeterministicExecutor(),
    )
    command = SubmitTurnCommand(
        conversation_id=f"conversation-{uuid.uuid4().hex}",
        question="fail completion",
        idempotency_key="atomic-completion",
    )
    submission = await runtime.submit_turn(identity=runtime_identity, command=command)
    await _install_event_failure_trigger(test_maintenance_engine, "RUN_COMPLETED")
    try:
        with pytest.raises(Exception, match="forced T12 atomicity failure"):
            async for _ in runtime.execute(
                identity=runtime_identity,
                submission=submission,
                question=command.question,
            ):
                pass
    finally:
        await _remove_event_failure_trigger(test_maintenance_engine)

    recovered = await runtime.get_run(
        identity=runtime_identity,
        conversation_id=command.conversation_id,
        run_id=submission.run_id,
    )
    async with async_session_maker() as session:
        assistant_messages = await session.exec(
            select(func.count())
            .select_from(MessageCard)
            .where(
                MessageCard.run_id == submission.run_id,
                MessageCard.sender_type == "agent",
            )
        )

    assert recovered.status is RunStatus.FAILED
    assert recovered.final_answer is None
    assert assistant_messages.one() == 0
