"""Tenant existence and operational-status resolution."""

from __future__ import annotations

import logging
from enum import StrEnum

from sqlmodel import Session
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.tenancy import (
    TenantContext,
    TenantContextMissingError,
    TenantDisabledError,
    TenantStatus,
    TenantSuspendedError,
    TenantUnknownError,
    validate_tenant_id,
)
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)


class TenantAccessMode(StrEnum):
    """Kinds of tenant operation considered by status policy."""

    READ = "READ"
    BUSINESS = "BUSINESS"
    BACKGROUND = "BACKGROUND"


def _resolved_context(tenant: Tenant, mode: TenantAccessMode) -> TenantContext:
    status = TenantStatus(tenant.status)
    if status == TenantStatus.DISABLED:
        _log_resolution_failure(TenantDisabledError.code, tenant.id, mode)
        raise TenantDisabledError("Tenant is disabled")
    if status == TenantStatus.SUSPENDED and mode != TenantAccessMode.READ:
        _log_resolution_failure(TenantSuspendedError.code, tenant.id, mode)
        raise TenantSuspendedError("Tenant is suspended for new operations")
    return TenantContext(
        tenant_id=tenant.id,
        slug=tenant.slug,
        display_name=tenant.display_name,
        status=status,
    )


def _canonical_candidate(tenant_id: str | None, mode: TenantAccessMode) -> str:
    if tenant_id is None or not tenant_id.strip():
        _log_resolution_failure(TenantContextMissingError.code, "<missing>", mode)
        raise TenantContextMissingError("Tenant identity is required")
    return validate_tenant_id(tenant_id)


def tenant_id_from_request(tenant_id: str | None) -> str:
    """Resolve explicit request identity with a local-only bootstrap fallback."""
    if tenant_id is not None:
        return validate_tenant_id(tenant_id)
    if settings.ENVIRONMENT.lower() not in {"development", "test", "local"}:
        _log_resolution_failure(
            TenantContextMissingError.code,
            "<missing>",
            TenantAccessMode.BUSINESS,
        )
        raise TenantContextMissingError("Tenant identity is required")
    return validate_tenant_id(settings.LOCAL_BOOTSTRAP_TENANT_ID)


def _log_resolution_failure(code: str, tenant_id: str, mode: TenantAccessMode) -> None:
    logger.warning(
        "Tenant resolution rejected",
        extra={
            "event": code,
            "tenant_id": tenant_id,
            "operation": mode.value,
            "resource_type": "tenant",
        },
    )


class TenantResolver:
    """Resolve trusted tenant identity using an asynchronous database session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def resolve(
        self,
        tenant_id: str | None,
        *,
        mode: TenantAccessMode = TenantAccessMode.BUSINESS,
    ) -> TenantContext:
        """Return the canonical tenant context or fail closed."""
        canonical_id = _canonical_candidate(tenant_id, mode)
        tenant = await self._session.get(Tenant, canonical_id)
        if tenant is None:
            _log_resolution_failure(TenantUnknownError.code, canonical_id, mode)
            raise TenantUnknownError("Tenant does not exist")
        return _resolved_context(tenant, mode)


def resolve_tenant_sync(
    session: Session,
    tenant_id: str | None,
    *,
    mode: TenantAccessMode = TenantAccessMode.BACKGROUND,
) -> TenantContext:
    """Resolve tenant identity at a synchronous worker boundary."""
    canonical_id = _canonical_candidate(tenant_id, mode)
    tenant = session.get(Tenant, canonical_id)
    if tenant is None:
        _log_resolution_failure(TenantUnknownError.code, canonical_id, mode)
        raise TenantUnknownError("Tenant does not exist")
    return _resolved_context(tenant, mode)
