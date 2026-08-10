"""Shared tenant-scoped SQLModel base."""

from sqlmodel import Field, SQLModel

from app.core.tenancy import get_current_tenant_id


class TenantScopedModel(SQLModel):
    """Base for records that must never cross a tenant boundary."""

    tenant_id: str = Field(
        default_factory=get_current_tenant_id,
        index=True,
        max_length=64,
        description="Tenant namespace",
    )
