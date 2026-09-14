"""Tenant-owned compliance audit, approval, and sensitive-export records."""

from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import JSON, Column, DateTime, String, Text, UniqueConstraint, text
from sqlmodel import Field

from app.core.utils import utc_now
from app.models.tenant import TenantScopedModel


class ApprovalStatus(StrEnum):
    """Lifecycle states for an exact sensitive operation approval."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    EXECUTED = "EXECUTED"


class ComplianceAuditEvent(TenantScopedModel, table=True):
    """Minimal append-only evidence for compliance lifecycle operations."""

    __tablename__ = "compliance_audit_events"

    id: int | None = Field(default=None, primary_key=True)
    event_type: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    actor_user_id: int | None = Field(default=None, index=True)
    actor_type: str = Field(max_length=24)
    target_type: str = Field(max_length=64, index=True)
    target_reference: str | None = Field(default=None, max_length=128)
    outcome: str = Field(max_length=24, index=True)
    reason_code: str = Field(max_length=64)
    correlation_id: str = Field(max_length=128, index=True)
    event_metadata: dict[str, object] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
        ),
    )


class ApprovalRequest(TenantScopedModel, table=True):
    """Exact, expiring, tenant-bound approval for a sensitive operation."""

    __tablename__ = "approval_requests"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    operation_type: str = Field(max_length=64, index=True)
    requester_user_id: int = Field(foreign_key="users.id", index=True)
    status: ApprovalStatus = Field(
        default=ApprovalStatus.PENDING, sa_column=Column(String(16), nullable=False, index=True)
    )
    operation_payload_hash: str = Field(max_length=64, index=True)
    operation_parameters: dict[str, object] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    requested_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
        ),
    )
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True)
    )
    approver_user_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    decision_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    executed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    correlation_id: str = Field(max_length=128, index=True)


class SensitiveExportArtifact(TenantScopedModel, table=True):
    """Short-lived tenant-owned result for idempotent sensitive export delivery."""

    __tablename__ = "sensitive_export_artifacts"
    __table_args__ = (UniqueConstraint("approval_request_id", name="uq_sensitive_export_approval"),)

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    approval_request_id: str = Field(foreign_key="approval_requests.id", index=True, max_length=36)
    operation_payload_hash: str = Field(max_length=64)
    filename: str = Field(max_length=160)
    media_type: str = Field(default="text/csv", max_length=64)
    content: str = Field(sa_column=Column(Text, nullable=False))
    record_count: int = Field(ge=0)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
        ),
    )
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True)
    )
