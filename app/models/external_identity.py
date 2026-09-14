"""Durable bindings between local users and external identities."""

from datetime import datetime

from sqlalchemy import Column, DateTime, String, UniqueConstraint, text
from sqlmodel import Field

from app.core.utils import utc_now
from app.models.tenant import TenantScopedModel


class ExternalIdentity(TenantScopedModel, table=True):
    """Bind one OIDC issuer/subject pair to one local user."""

    __tablename__ = "external_identities"
    __table_args__ = (
        UniqueConstraint("issuer", "subject", name="uq_external_identities_issuer_subject"),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    provider: str = Field(
        sa_column=Column(String(64), nullable=False),
        description="Configured identity-provider label",
    )
    issuer: str = Field(
        sa_column=Column(String(512), nullable=False),
        description="Canonical OIDC issuer",
    )
    subject: str = Field(
        sa_column=Column(String(255), nullable=False),
        description="Stable provider subject",
    )
    email_at_link_time: str | None = Field(
        default=None,
        sa_column=Column(String(320), nullable=True),
        description="Informational verified email observed when the link was created",
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
        ),
    )
    last_authenticated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
        ),
    )
