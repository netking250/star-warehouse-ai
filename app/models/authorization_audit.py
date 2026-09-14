"""Tenant-owned audit evidence for application authorization mutations."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import Column, DateTime, String, text
from sqlmodel import Field

from app.core.utils import utc_now
from app.models.tenant import TenantScopedModel


class AuthorizationAuditAction(StrEnum):
    """Security-relevant authorization state mutations."""

    ROLE_ASSIGNED = "role.assigned"
    ROLE_REVOKED = "role.revoked"
    MEMBERSHIP_ENABLED = "membership.enabled"
    MEMBERSHIP_DISABLED = "membership.disabled"


class AuthorizationAuditEvent(TenantScopedModel, table=True):
    """Atomic evidence written with an authorization state mutation."""

    __tablename__ = "authorization_audit_events"

    id: int | None = Field(default=None, primary_key=True)
    actor_user_id: int = Field(foreign_key="users.id", index=True)
    target_user_id: int = Field(foreign_key="users.id", index=True)
    action: AuthorizationAuditAction = Field(
        sa_column=Column(String(32), nullable=False, index=True)
    )
    previous_role: str | None = Field(default=None, max_length=32)
    new_role: str | None = Field(default=None, max_length=32)
    previous_active: bool | None = Field(default=None)
    new_active: bool | None = Field(default=None)
    decision: str = Field(default="ALLOW", max_length=16)
    reason_code: str = Field(default="ALLOW", max_length=64)
    correlation_id: str = Field(max_length=128, index=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
        ),
    )
