"""Durable persistence models for conversation execution."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    Index,
    UniqueConstraint,
    text,
)
from sqlmodel import Field

from app.conversation.state_machine import RunStatus
from app.core.utils import utc_now
from app.models.tenant import TenantScopedModel


class RuntimeEventType(StrEnum):
    """Durable low-frequency conversation runtime event types."""

    TURN_ACCEPTED = "TURN_ACCEPTED"
    RUN_STARTED = "RUN_STARTED"
    TOOL_REQUESTED = "TOOL_REQUESTED"
    TOOL_STARTED = "TOOL_STARTED"
    TOOL_COMPLETED = "TOOL_COMPLETED"
    TOOL_FAILED = "TOOL_FAILED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    RUN_COMPLETED = "RUN_COMPLETED"
    RUN_FAILED = "RUN_FAILED"
    RUN_CANCELLED = "RUN_CANCELLED"
    STALE_RESULT_IGNORED = "STALE_RESULT_IGNORED"


class ToolExecutionStatus(StrEnum):
    """Lifecycle of one durable asynchronous tool invocation."""

    REQUESTED = "REQUESTED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Conversation(TenantScopedModel, table=True):
    """Durable tenant-owned conversation metadata and optimistic revision."""

    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "conversation_id", name="uq_conversations_identity"),
        Index("ix_conversations_owner", "tenant_id", "user_id", "updated_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    conversation_id: str = Field(max_length=128)
    user_id: int = Field(foreign_key="users.id", index=True)
    revision: int = Field(default=0, ge=0)
    active_run_id: str | None = Field(default=None, max_length=36, index=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
        ),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
            onupdate=text("CURRENT_TIMESTAMP"),
        ),
    )


class ConversationTurn(TenantScopedModel, table=True):
    """One logical user input and its resulting assistant lifecycle."""

    __tablename__ = "conversation_turns"
    __table_args__ = (
        UniqueConstraint("tenant_id", "turn_id", name="uq_conversation_turns_identity"),
        UniqueConstraint(
            "tenant_id",
            "conversation_id",
            "idempotency_key",
            name="uq_conversation_turns_submission",
        ),
        Index("ix_conversation_turns_order", "tenant_id", "conversation_id", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    turn_id: str = Field(max_length=36)
    conversation_id: str = Field(max_length=128)
    user_id: int = Field(foreign_key="users.id", index=True)
    idempotency_key: str = Field(max_length=192)
    current_run_id: str = Field(max_length=36, index=True)
    status: str = Field(default=RunStatus.PENDING, max_length=24, index=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
        ),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
            onupdate=text("CURRENT_TIMESTAMP"),
        ),
    )


class ConversationRun(TenantScopedModel, table=True):
    """One durable execution attempt for a conversation turn."""

    __tablename__ = "conversation_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "run_id", name="uq_conversation_runs_identity"),
        UniqueConstraint("tenant_id", "turn_id", "attempt", name="uq_conversation_runs_attempt"),
        CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'WAITING_TOOL', 'WAITING_HUMAN', "
            "'COMPLETED', 'FAILED', 'CANCELLED')",
            name="ck_conversation_runs_status",
        ),
        Index("ix_conversation_runs_recovery", "tenant_id", "status", "updated_at"),
        Index("ix_conversation_runs_conversation", "tenant_id", "conversation_id", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    run_id: str = Field(max_length=36)
    turn_id: str = Field(max_length=36)
    conversation_id: str = Field(max_length=128)
    user_id: int = Field(foreign_key="users.id", index=True)
    correlation_id: str = Field(max_length=128, index=True)
    trace_id: str | None = Field(default=None, max_length=64)
    attempt: int = Field(default=1, ge=1)
    status: str = Field(default=RunStatus.PENDING, max_length=24, index=True)
    revision: int = Field(default=0, ge=0)
    conversation_revision: int = Field(default=0, ge=0)
    next_event_sequence: int = Field(default=1, ge=1)
    final_message_id: int | None = Field(
        default=None,
        foreign_key="message_cards.id",
        ondelete="SET NULL",
    )
    failure_category: str | None = Field(default=None, max_length=64)
    failure_metadata: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
        ),
    )
    started_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    cancelled_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
            onupdate=text("CURRENT_TIMESTAMP"),
        ),
    )


class ConversationRuntimeEvent(TenantScopedModel, table=True):
    """Ordered durable lifecycle event for one conversation run."""

    __tablename__ = "conversation_runtime_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "event_id", name="uq_runtime_events_identity"),
        UniqueConstraint("tenant_id", "run_id", "sequence", name="uq_runtime_events_sequence"),
        UniqueConstraint("tenant_id", "run_id", "event_key", name="uq_runtime_events_key"),
        Index("ix_runtime_events_replay", "tenant_id", "run_id", "sequence"),
    )

    id: int | None = Field(default=None, primary_key=True)
    event_id: str = Field(max_length=36)
    conversation_id: str = Field(max_length=128)
    turn_id: str = Field(max_length=36)
    run_id: str = Field(max_length=36)
    sequence: int = Field(ge=1)
    event_key: str = Field(max_length=192)
    event_type: str = Field(max_length=48, index=True)
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    correlation_id: str = Field(max_length=128, index=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
        ),
    )


class ConversationToolExecution(TenantScopedModel, table=True):
    """Durable identity and result-acceptance state for one asynchronous tool call."""

    __tablename__ = "conversation_tool_executions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "tool_execution_id", name="uq_tool_executions_identity"),
        UniqueConstraint(
            "tenant_id", "run_id", "idempotency_key", name="uq_tool_executions_idempotency"
        ),
        CheckConstraint(
            "status IN ('REQUESTED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED')",
            name="ck_tool_executions_status",
        ),
        Index("ix_tool_executions_run", "tenant_id", "run_id", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    tool_execution_id: str = Field(max_length=36)
    conversation_id: str = Field(max_length=128)
    turn_id: str = Field(max_length=36)
    run_id: str = Field(max_length=36)
    user_id: int = Field(foreign_key="users.id", index=True)
    tool_name: str = Field(max_length=128)
    idempotency_key: str = Field(max_length=192)
    status: str = Field(default=ToolExecutionStatus.REQUESTED, max_length=24, index=True)
    expected_run_revision: int = Field(ge=0)
    result_delivery_id: str | None = Field(default=None, max_length=192)
    result_payload: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )
    failure_category: str | None = Field(default=None, max_length=64)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
        ),
    )
    started_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
            onupdate=text("CURRENT_TIMESTAMP"),
        ),
    )
