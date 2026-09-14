"""Fixtures and deterministic adapters for conversation runtime tests."""

import asyncio
import uuid
from collections.abc import AsyncIterator

import pytest_asyncio

from app.conversation.contracts import (
    ConversationIdentity,
    ExecutionRequest,
    ExecutorEvent,
    ExecutorEventType,
)
from app.core.database import async_session_maker
from app.core.tenancy import get_current_tenant_id
from app.models.user import User


class DeterministicExecutor:
    """Return one deterministic answer and expose execution count."""

    def __init__(self, answer: str = "deterministic answer") -> None:
        self.answer = answer
        self.executions = 0

    async def execute(self, request: ExecutionRequest) -> AsyncIterator[ExecutorEvent]:
        self.executions += 1
        yield ExecutorEvent(ExecutorEventType.TOKEN, {"token": self.answer})
        yield ExecutorEvent(
            ExecutorEventType.COMPLETED,
            {"answer": self.answer, "metadata": {"agent": "deterministic"}},
        )


class BlockingExecutor:
    """Pause deterministic execution until the test releases it."""

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.executions = 0

    async def execute(self, request: ExecutionRequest) -> AsyncIterator[ExecutorEvent]:
        self.executions += 1
        self.started.set()
        await self.release.wait()
        yield ExecutorEvent(
            ExecutorEventType.COMPLETED,
            {"answer": f"answer:{request.conversation_id}"},
        )


class ConcurrentExecutor:
    """Prove two different conversations can be inside execution together."""

    def __init__(self) -> None:
        self.started_count = 0
        self.both_started = asyncio.Event()

    async def execute(self, request: ExecutionRequest) -> AsyncIterator[ExecutorEvent]:
        self.started_count += 1
        if self.started_count == 2:
            self.both_started.set()
        await asyncio.wait_for(self.both_started.wait(), timeout=2)
        yield ExecutorEvent(
            ExecutorEventType.COMPLETED,
            {"answer": f"answer:{request.conversation_id}"},
        )


class FailingExecutor:
    """Raise one deterministic executor failure."""

    async def execute(self, request: ExecutionRequest) -> AsyncIterator[ExecutorEvent]:
        raise RuntimeError("deterministic executor failure")
        yield


@pytest_asyncio.fixture(loop_scope="session")
async def runtime_identity() -> ConversationIdentity:
    """Persist one user in the currently bound test tenant."""
    tenant_id = get_current_tenant_id()
    suffix = uuid.uuid4().hex[:10]
    async with async_session_maker() as session:
        user = User(
            username=f"runtime_{suffix}",
            password_hash=User.hash_password("password123"),
            email=f"runtime_{suffix}@example.test",
            full_name="Runtime Test",
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        assert user.id is not None
        return ConversationIdentity(
            tenant_id=tenant_id,
            user_id=user.id,
            correlation_id=f"runtime-correlation-{suffix}",
            trace_id=None,
        )
