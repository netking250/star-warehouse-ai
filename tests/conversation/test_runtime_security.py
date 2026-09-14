"""Tenant and actor isolation at conversation runtime control boundaries."""

import uuid

import pytest
from sqlalchemy import text

from app.conversation.contracts import (
    ConversationIdentity,
    SubmitTurnCommand,
    ToolResultEnvelope,
)
from app.conversation.runtime import ConversationNotFoundError, ConversationRuntime
from app.core.database import async_session_maker
from app.core.tenancy import TenantIsolationError, tenant_scope
from app.models.user import User
from tests.conversation.conftest import DeterministicExecutor


async def _create_tenant_identity(test_maintenance_engine) -> ConversationIdentity:
    tenant_id = f"runtime-tenant-{uuid.uuid4().hex[:12]}"
    async with test_maintenance_engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO tenants (id, slug, display_name, status) "
                "VALUES (:tenant_id, :tenant_id, 'Runtime Tenant', 'ACTIVE')"
            ),
            {"tenant_id": tenant_id},
        )
    with tenant_scope(tenant_id):
        async with async_session_maker() as session:
            user = User(
                username=f"user-{uuid.uuid4().hex[:10]}",
                password_hash=User.hash_password("password123"),
                email=f"{uuid.uuid4().hex}@example.test",
                full_name="Isolated Runtime User",
                is_active=True,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            assert user.id is not None
            return ConversationIdentity(
                tenant_id=tenant_id,
                user_id=user.id,
                correlation_id=f"correlation-{uuid.uuid4().hex}",
            )


@pytest.mark.asyncio
async def test_same_submission_key_and_conversation_are_isolated_between_tenants(
    runtime_identity,
    test_maintenance_engine,
) -> None:
    runtime = ConversationRuntime(
        session_factory=async_session_maker,
        executor=DeterministicExecutor(),
    )
    other_identity = await _create_tenant_identity(test_maintenance_engine)
    command = SubmitTurnCommand(
        conversation_id=f"shared-conversation-{uuid.uuid4().hex}",
        question="same logical client key",
        idempotency_key="shared-idempotency-key",
    )
    first = await runtime.submit_turn(identity=runtime_identity, command=command)

    with tenant_scope(other_identity.tenant_id):
        with pytest.raises(ConversationNotFoundError):
            await runtime.get_run(
                identity=other_identity,
                conversation_id=command.conversation_id,
                run_id=first.run_id,
            )
        with pytest.raises(ConversationNotFoundError):
            await runtime.cancel_run(
                identity=other_identity,
                conversation_id=command.conversation_id,
                run_id=first.run_id,
            )
        with pytest.raises(ConversationNotFoundError):
            await runtime.replay_events(
                identity=other_identity,
                conversation_id=command.conversation_id,
                run_id=first.run_id,
            )
        second = await runtime.submit_turn(identity=other_identity, command=command)

    assert first.run_id != second.run_id
    assert first.turn_id != second.turn_id


@pytest.mark.asyncio
async def test_cross_tenant_tool_result_identity_is_rejected_before_lookup(
    runtime_identity,
    test_maintenance_engine,
) -> None:
    runtime = ConversationRuntime(
        session_factory=async_session_maker,
        executor=DeterministicExecutor(),
    )
    other_identity = await _create_tenant_identity(test_maintenance_engine)

    with tenant_scope(other_identity.tenant_id), pytest.raises(TenantIsolationError):
        await runtime.accept_tool_result(
            identity=other_identity,
            envelope=ToolResultEnvelope(
                tenant_id=runtime_identity.tenant_id,
                user_id=runtime_identity.user_id,
                conversation_id="foreign-conversation",
                turn_id=str(uuid.uuid4()),
                run_id=str(uuid.uuid4()),
                tool_execution_id=str(uuid.uuid4()),
                correlation_id=runtime_identity.correlation_id,
                delivery_id="foreign-delivery",
                expected_run_revision=1,
                succeeded=True,
            ),
        )
