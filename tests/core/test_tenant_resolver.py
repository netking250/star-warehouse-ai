"""Behavior tests for canonical tenant resolution."""

import uuid

import pytest

from app.core.config import settings
from app.core.tenancy import (
    TenantContextMissingError,
    TenantDisabledError,
    TenantStatus,
    TenantSuspendedError,
    TenantUnknownError,
)
from app.core.tenant_resolver import TenantResolver, tenant_id_from_request
from app.models.tenant import Tenant


def test_production_request_cannot_fall_back_to_default_tenant(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    with pytest.raises(TenantContextMissingError):
        tenant_id_from_request(None)


@pytest.mark.asyncio
async def test_tenant_resolver_returns_canonical_active_context(db_session) -> None:
    tenant_id = f"tenant-resolver-{uuid.uuid4().hex[:8]}"
    tenant = Tenant(
        id=tenant_id,
        slug=tenant_id,
        display_name="Resolver Tenant",
        status=TenantStatus.ACTIVE,
    )
    db_session.add(tenant)
    await db_session.flush()

    context = await TenantResolver(db_session).resolve(tenant_id)

    assert context.tenant_id == tenant_id
    assert context.slug == tenant_id
    assert context.display_name == "Resolver Tenant"
    assert context.status == TenantStatus.ACTIVE


@pytest.mark.asyncio
async def test_tenant_resolver_missing_tenant_fails_closed(db_session) -> None:
    with pytest.raises(TenantContextMissingError):
        await TenantResolver(db_session).resolve(None)


@pytest.mark.asyncio
async def test_tenant_resolver_unknown_tenant_fails_closed(db_session) -> None:
    with pytest.raises(TenantUnknownError):
        await TenantResolver(db_session).resolve(f"tenant-unknown-{uuid.uuid4().hex[:8]}")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tenant_status", "expected_error"),
    [
        (TenantStatus.SUSPENDED, TenantSuspendedError),
        (TenantStatus.DISABLED, TenantDisabledError),
    ],
)
async def test_tenant_resolver_inactive_tenant_blocks_business_operations(
    db_session,
    tenant_status: TenantStatus,
    expected_error: type[RuntimeError],
) -> None:
    tenant_id = f"tenant-{tenant_status.value.lower()}-{uuid.uuid4().hex[:8]}"
    db_session.add(
        Tenant(
            id=tenant_id,
            slug=tenant_id,
            display_name="Inactive Tenant",
            status=tenant_status,
        )
    )
    await db_session.flush()

    with pytest.raises(expected_error):
        await TenantResolver(db_session).resolve(tenant_id)


@pytest.mark.asyncio
async def test_login_unknown_tenant_is_rejected_before_authentication(client) -> None:
    response = await client.post(
        "/api/v1/login",
        json={
            "username": "unknown-tenant-user",
            "password": "password123",
            "tenant_id": f"tenant-unknown-{uuid.uuid4().hex[:8]}",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "tenant_unknown"
