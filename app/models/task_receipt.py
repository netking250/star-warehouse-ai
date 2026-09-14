"""Persistent consumer receipts for duplicate-safe task execution."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import JsonValue
from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlmodel import Field, SQLModel

from app.core.utils import utc_now


class TaskReceiptStatus(StrEnum):
    """Recoverable lifecycle of a protected consumer execution."""

    PROCESSING = "PROCESSING"
    RETRYABLE = "RETRYABLE"
    COMPLETED = "COMPLETED"
    TERMINAL = "TERMINAL"


class TaskExecutionReceipt(SQLModel, table=True):
    """Durable identity and outcome for one logical tenant task execution."""

    __tablename__ = "task_execution_receipts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PROCESSING', 'RETRYABLE', 'COMPLETED', 'TERMINAL')",
            name="ck_task_execution_receipts_status",
        ),
        UniqueConstraint(
            "tenant_id",
            "handler",
            "idempotency_key",
            name="uq_task_execution_receipts_identity",
        ),
        Index(
            "ix_task_execution_receipts_recovery",
            "status",
            "claim_expires_at",
            "updated_at",
        ),
    )

    receipt_id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, nullable=False),
    )
    tenant_id: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    handler: str = Field(sa_column=Column(String(192), nullable=False))
    idempotency_key: str = Field(sa_column=Column(String(192), nullable=False))
    status: TaskReceiptStatus = Field(
        default=TaskReceiptStatus.PROCESSING,
        sa_column=Column(String(32), nullable=False),
    )
    attempt_count: int = Field(default=0, nullable=False)
    claim_token: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(UUID(as_uuid=True), nullable=True),
    )
    claim_expires_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    result: dict[str, JsonValue] | None = Field(
        default=None,
        sa_column=Column(JSON().with_variant(JSONB, "postgresql"), nullable=True),
    )
    failure_code: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    last_error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
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
    completed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    model_config = {"use_enum_values": True}
