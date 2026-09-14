"""Tenant domain entity and shared tenant-scoped SQLModel base."""

from datetime import datetime

from sqlalchemy import Column, DateTime, String, UniqueConstraint, text
from sqlmodel import Field, SQLModel

from app.core.tenancy import TenantStatus, get_current_tenant_id, validate_tenant_id
from app.core.utils import utc_now


class Tenant(SQLModel, table=True):
    """Operational tenant identity used for isolation and status enforcement."""

    __tablename__ = "tenants"
    __table_args__ = (UniqueConstraint("slug", name="uq_tenants_slug"),)

    id: str = Field(primary_key=True, max_length=64)
    slug: str = Field(max_length=64)
    display_name: str = Field(max_length=128)
    status: TenantStatus = Field(
        default=TenantStatus.ACTIVE,
        sa_column=Column(String(16), nullable=False, index=True),
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

    def model_post_init(self, __context: object) -> None:
        """Validate persisted identifiers with the canonical tenant rules."""
        validate_tenant_id(self.id)
        validate_tenant_id(self.slug)


class TenantScopedModel(SQLModel):
    """Base for records that must never cross a tenant boundary."""

    tenant_id: str = Field(
        default_factory=get_current_tenant_id,
        index=True,
        max_length=64,
        description="Tenant namespace",
    )
