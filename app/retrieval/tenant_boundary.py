"""Tenant-aware Qdrant payload and filter builders."""

from collections.abc import Mapping

from qdrant_client import models

from app.core.tenancy import TenantIsolationError, get_current_tenant_id, validate_tenant_id


def active_vector_tenant(tenant_id: str | None = None) -> str:
    """Return the active tenant and reject a conflicting explicit identifier."""
    active_tenant = get_current_tenant_id()
    if tenant_id is None:
        return active_tenant
    requested_tenant = validate_tenant_id(tenant_id)
    if requested_tenant != active_tenant:
        raise TenantIsolationError("Cannot access vectors for another tenant")
    return active_tenant


def tenant_payload(
    payload: Mapping[str, object], *, tenant_id: str | None = None
) -> dict[str, object]:
    """Add the active tenant to a vector payload without allowing overrides."""
    active_tenant = active_vector_tenant(tenant_id)
    payload_tenant = payload.get("tenant_id")
    if payload_tenant is not None and payload_tenant != active_tenant:
        raise TenantIsolationError("Cannot write a vector payload for another tenant")
    return {**payload, "tenant_id": active_tenant}


def tenant_filter(*conditions: models.Condition, tenant_id: str | None = None) -> models.Filter:
    """Build a Qdrant filter that always includes the active tenant boundary."""
    active_tenant = active_vector_tenant(tenant_id)
    return models.Filter(
        must=[
            models.FieldCondition(key="tenant_id", match=models.MatchValue(value=active_tenant)),
            *conditions,
        ]
    )


def tenant_filter_selector(
    *conditions: models.Condition, tenant_id: str | None = None
) -> models.FilterSelector:
    """Build a tenant-filtered Qdrant delete selector."""
    return models.FilterSelector(filter=tenant_filter(*conditions, tenant_id=tenant_id))
