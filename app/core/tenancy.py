"""Tenant context propagation and namespace helpers."""

import contextvars
import re
from collections.abc import Iterator
from contextlib import contextmanager

from app.core.config import settings

_TENANT_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")
_tenant_id: contextvars.ContextVar[str] = contextvars.ContextVar("tenant_id", default="default")


class TenantIsolationError(RuntimeError):
    """Raised when data crosses the active tenant boundary."""


def validate_tenant_id(tenant_id: str) -> str:
    """Validate and return a tenant identifier safe for namespaces."""
    if not _TENANT_PATTERN.fullmatch(tenant_id):
        raise ValueError(
            "tenant_id must start with an alphanumeric character and contain only "
            "letters, digits, underscores, or hyphens"
        )
    return tenant_id


def get_current_tenant_id() -> str:
    """Return the tenant bound to the current async execution context."""
    return _tenant_id.get()


def set_current_tenant_id(tenant_id: str) -> contextvars.Token[str]:
    """Bind a validated tenant to the current execution context."""
    return _tenant_id.set(validate_tenant_id(tenant_id))


def reset_current_tenant_id(token: contextvars.Token[str]) -> None:
    """Restore a previously active tenant context."""
    _tenant_id.reset(token)


@contextmanager
def tenant_scope(tenant_id: str) -> Iterator[None]:
    """Temporarily bind database, cache, and vector operations to one tenant."""
    token = set_current_tenant_id(tenant_id)
    try:
        yield
    finally:
        reset_current_tenant_id(token)


def namespaced_key(key: str, tenant_id: str | None = None) -> str:
    """Prefix a storage key with environment and tenant namespaces."""
    tenant = validate_tenant_id(tenant_id or get_current_tenant_id())
    return f"{settings.ENVIRONMENT}:{tenant}:{key}"


def namespaced_collection(collection: str) -> str:
    """Prefix a Qdrant collection with the deployment environment."""
    normalized = re.sub(r"[^a-zA-Z0-9_-]", "_", collection)
    return f"{settings.ENVIRONMENT}_{normalized}"
