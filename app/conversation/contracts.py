"""Typed public interface contracts for durable conversation execution."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.conversation.state_machine import RunStatus
from app.task_runtime.context import TaskContext


class ExecutorEventType(StrEnum):
    """Transport-independent events emitted by a conversation executor adapter."""

    TOKEN = "TOKEN"
    METADATA = "METADATA"
    COMPLETED = "COMPLETED"


@dataclass(frozen=True, slots=True)
class ConversationIdentity:
    """Trusted tenant and actor identity for one runtime command."""

    tenant_id: str
    user_id: int
    correlation_id: str
    trace_id: str | None = None


class SubmitTurnCommand(BaseModel):
    """One idempotent logical user-message submission."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    conversation_id: str = Field(min_length=1, max_length=128)
    question: str = Field(min_length=1, max_length=500)
    idempotency_key: str = Field(min_length=1, max_length=192)


@dataclass(frozen=True, slots=True)
class TurnSubmission:
    """Stable identities returned for a submitted or replayed turn."""

    conversation_id: str
    turn_id: str
    run_id: str
    status: RunStatus
    run_revision: int
    created: bool


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    """Executor input independent of LangGraph types and checkpoint representation."""

    tenant_id: str
    user_id: int
    conversation_id: str
    turn_id: str
    run_id: str
    correlation_id: str
    trace_id: str | None
    question: str
    intent_category: str | None = None
    experiment_variant_id: int | None = None
    memory_context_config: dict[str, Any] | None = None
    variant_llm_model: str | None = None
    variant_retriever_top_k: int | None = None
    variant_reranker_enabled: bool | None = None


@dataclass(frozen=True, slots=True)
class ExecutorEvent:
    """One executor event before runtime persistence/ordering is applied."""

    event_type: ExecutorEventType
    payload: dict[str, Any] = field(default_factory=dict)


class ConversationExecutor(Protocol):
    """Port implemented by the current LangGraph adapter and deterministic tests."""

    def execute(self, request: ExecutionRequest) -> AsyncIterator[ExecutorEvent]:
        """Execute one accepted run and emit transport-independent events."""
        ...


@dataclass(frozen=True, slots=True)
class RuntimeEvent:
    """One normalized event emitted by the durable conversation runtime."""

    event_type: str
    conversation_id: str
    turn_id: str
    run_id: str
    payload: dict[str, Any]
    sequence: int | None = None
    event_id: str | None = None
    durable: bool = True


@dataclass(frozen=True, slots=True)
class RunSnapshot:
    """Durable run status and final logical assistant result, if present."""

    conversation_id: str
    turn_id: str
    run_id: str
    status: RunStatus
    revision: int
    conversation_revision: int
    final_answer: str | None
    failure_category: str | None


@dataclass(frozen=True, slots=True)
class CancellationResult:
    """Explicit outcome of an idempotent cancellation request."""

    run: RunSnapshot
    outcome: str


@dataclass(frozen=True, slots=True)
class ToolInvocation:
    """Durable asynchronous tool identity plus trusted task context."""

    tool_execution_id: str
    run_id: str
    turn_id: str
    conversation_id: str
    tool_name: str
    expected_run_revision: int
    task_context: TaskContext
    duplicate: bool = False


class ToolResultEnvelope(BaseModel):
    """Trusted identity required to accept one asynchronous tool result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant_id: str = Field(min_length=1, max_length=64)
    user_id: int = Field(gt=0)
    conversation_id: str = Field(min_length=1, max_length=128)
    turn_id: str = Field(min_length=1, max_length=36)
    run_id: str = Field(min_length=1, max_length=36)
    tool_execution_id: str = Field(min_length=1, max_length=36)
    correlation_id: str = Field(min_length=1, max_length=128)
    delivery_id: str = Field(min_length=1, max_length=192)
    expected_run_revision: int = Field(ge=0)
    succeeded: bool
    result: dict[str, Any] = Field(default_factory=dict)
    failure_category: str | None = Field(default=None, max_length=64)


@dataclass(frozen=True, slots=True)
class ToolResultAcceptance:
    """Outcome of applying or rejecting an asynchronous tool result."""

    accepted: bool
    duplicate: bool
    reason: str
    run: RunSnapshot
