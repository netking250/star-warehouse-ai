"""Persistent records for transactional asynchronous intent."""

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


class OutboxStatus(StrEnum):
    """Minimal lifecycle for an outbox event."""

    PENDING = "PENDING"
    PUBLISHING = "PUBLISHING"
    PUBLISHED = "PUBLISHED"


class OutboxEvent(SQLModel, table=True):
    """A sanitized task envelope persisted with its business transaction.

    This operational table is intentionally not a ``TenantScopedModel`` because
    the relay must scan all tenants. Tenant enforcement lives in the enqueue
    interface, while the explicit non-defaulted ``tenant_id`` remains durable.
    """

    __tablename__ = "outbox_events"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'PUBLISHING', 'PUBLISHED')",
            name="ck_outbox_events_status",
        ),
        UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_outbox_events_tenant_idempotency"
        ),
        Index("ix_outbox_events_relay_eligible", "status", "available_at", "created_at"),
    )

    event_id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, nullable=False),
    )
    tenant_id: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    event_type: str = Field(sa_column=Column(String(128), nullable=False))
    aggregate_type: str = Field(sa_column=Column(String(64), nullable=False))
    aggregate_id: str = Field(sa_column=Column(String(128), nullable=False))
    task_name: str = Field(sa_column=Column(String(192), nullable=False))
    envelope: dict[str, JsonValue] = Field(
        sa_column=Column(JSON().with_variant(JSONB, "postgresql"), nullable=False)
    )
    idempotency_key: str = Field(sa_column=Column(String(192), nullable=False))
    status: OutboxStatus = Field(
        default=OutboxStatus.PENDING,
        sa_column=Column(String(32), nullable=False, server_default=OutboxStatus.PENDING.value),
    )
    attempt_count: int = Field(default=0, nullable=False)
    available_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
        ),
    )
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
    published_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    last_error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    claim_token: uuid.UUID | None = Field(
        default=None, sa_column=Column(UUID(as_uuid=True), nullable=True)
    )
    claim_expires_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    model_config = {"use_enum_values": True}
