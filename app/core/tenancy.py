"""Canonical tenant context and resource namespace primitives."""

from __future__ import annotations

import contextvars
import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath

from app.core.config import settings

_TENANT_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")
_RESOURCE_PATTERN = re.compile(r"^[^:\s][^\r\n]*$")


class TenantStatus(StrEnum):
    """Operational states supported by the tenant domain."""

    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DISABLED = "DISABLED"


@dataclass(frozen=True, slots=True)
class TenantContext:
    """Validated tenant identity bound to one request or task execution."""

    tenant_id: str
    slug: str
    display_name: str
    status: TenantStatus

    def __post_init__(self) -> None:
        validate_tenant_id(self.tenant_id)
        validate_tenant_id(self.slug)


class TenantAccessError(RuntimeError):
    """Base error for tenant resolution and access failures."""

    code = "tenant_access_denied"


class TenantContextMissingError(TenantAccessError):
    """Raised when tenant-owned work is attempted without tenant identity."""

    code = "tenant_missing"


class TenantUnknownError(TenantAccessError):
    """Raised when trusted tenant identity does not exist."""

    code = "tenant_unknown"


class TenantSuspendedError(TenantAccessError):
    """Raised when a suspended tenant attempts a new operation."""

    code = "tenant_suspended"


class TenantDisabledError(TenantAccessError):
    """Raised when a disabled tenant attempts any operation."""

    code = "tenant_disabled"


class TenantIsolationError(TenantAccessError):
    """Raised when data crosses the active tenant boundary."""

    code = "cross_tenant_access_denied"


_tenant_context: contextvars.ContextVar[TenantContext | None] = contextvars.ContextVar(
    "tenant_context", default=None
)


def validate_tenant_id(tenant_id: str) -> str:
    """Validate a case-sensitive canonical tenant identifier.

    Identifiers are preserved exactly for compatibility with existing data.
    They contain 1-64 ASCII letters, digits, underscores, or hyphens and start
    with an alphanumeric character.
    """
    if not _TENANT_PATTERN.fullmatch(tenant_id):
        raise ValueError(
            "tenant_id must start with an alphanumeric character and contain only "
            "letters, digits, underscores, or hyphens"
        )
    return tenant_id


def get_current_tenant_context() -> TenantContext:
    """Return the bound tenant context or fail closed when none is bound."""
    context = _tenant_context.get()
    if context is None:
        raise TenantContextMissingError("No tenant context is bound")
    return context


def get_current_tenant_id() -> str:
    """Return the canonical tenant identifier for the current execution."""
    return get_current_tenant_context().tenant_id


def get_optional_tenant_id() -> str | None:
    """Return the bound tenant identifier without inventing a fallback."""
    context = _tenant_context.get()
    return None if context is None else context.tenant_id


def set_current_tenant_context(
    tenant_context: TenantContext,
) -> contextvars.Token[TenantContext | None]:
    """Bind a resolved tenant context to the current async execution."""
    return _tenant_context.set(tenant_context)


def set_current_tenant_id(tenant_id: str) -> contextvars.Token[TenantContext | None]:
    """Bind an explicitly trusted tenant ID for tests and bootstrap code.

    Request and worker production paths must bind a resolver-produced
    :class:`TenantContext` with :func:`set_current_tenant_context` instead.
    """
    canonical_id = validate_tenant_id(tenant_id)
    return set_current_tenant_context(
        TenantContext(
            tenant_id=canonical_id,
            slug=canonical_id,
            display_name=canonical_id,
            status=TenantStatus.ACTIVE,
        )
    )


def clear_current_tenant() -> contextvars.Token[TenantContext | None]:
    """Clear tenant identity until a trusted resolver binds one."""
    return _tenant_context.set(None)


def reset_current_tenant(token: contextvars.Token[TenantContext | None]) -> None:
    """Restore the tenant context that preceded a binding operation."""
    _tenant_context.reset(token)


def reset_current_tenant_id(token: contextvars.Token[TenantContext | None]) -> None:
    """Backward-compatible alias for :func:`reset_current_tenant`."""
    reset_current_tenant(token)


@contextmanager
def tenant_scope(tenant: str | TenantContext) -> Iterator[None]:
    """Temporarily bind an explicit tenant for internal, test, or bootstrap work."""
    token = (
        set_current_tenant_id(tenant)
        if isinstance(tenant, str)
        else set_current_tenant_context(tenant)
    )
    try:
        yield
    finally:
        reset_current_tenant(token)


def _validate_resource_key(key: str) -> str:
    if not _RESOURCE_PATTERN.fullmatch(key):
        raise ValueError("resource key must be non-empty and contain no control characters")
    return key


@dataclass(frozen=True, slots=True)
class TenantNamespace:
    """Derive infrastructure resource names from one canonical tenant identity."""

    environment: str
    tenant_id: str | None

    @classmethod
    def current(cls) -> TenantNamespace:
        """Build a namespace for the currently bound tenant."""
        return cls.for_tenant(get_current_tenant_id())

    @classmethod
    def for_tenant(cls, tenant_id: str) -> TenantNamespace:
        """Build an explicit tenant namespace."""
        return cls(environment=settings.ENVIRONMENT, tenant_id=validate_tenant_id(tenant_id))

    @classmethod
    def system(cls) -> TenantNamespace:
        """Build the explicit system/global namespace."""
        return cls(environment=settings.ENVIRONMENT, tenant_id=None)

    def redis_key(self, logical_key: str) -> str:
        """Return a tenant or system Redis key."""
        key = _validate_resource_key(logical_key)
        if self.tenant_id is None:
            return f"{self.environment}:system:{key}"
        return f"{self.environment}:tenant:{self.tenant_id}:{key}"

    def storage_prefix(self) -> str:
        """Return the tenant-local object path prefix."""
        if self.tenant_id is None:
            return "system"
        return str(PurePosixPath("tenant", self.tenant_id))


def namespaced_key(key: str, tenant_id: str | None = None) -> str:
    """Build one Redis key from the current or explicit tenant namespace."""
    namespace = (
        TenantNamespace.current() if tenant_id is None else TenantNamespace.for_tenant(tenant_id)
    )
    return namespace.redis_key(key)


def namespaced_system_key(key: str) -> str:
    """Build one Redis key in the explicit system/global namespace."""
    return TenantNamespace.system().redis_key(key)


def all_tenant_key_pattern(logical_pattern: str) -> str:
    """Build a system-maintenance scan pattern spanning tenant namespaces."""
    pattern = _validate_resource_key(logical_pattern)
    return f"{settings.ENVIRONMENT}:tenant:*:{pattern}"


def parse_tenant_key(key: str) -> tuple[str, str]:
    """Return tenant identity and logical key from a namespaced Redis key."""
    prefix = f"{settings.ENVIRONMENT}:tenant:"
    if not key.startswith(prefix):
        raise ValueError("Redis key is not in the current tenant namespace")
    remainder = key[len(prefix) :]
    tenant_id, separator, logical_key = remainder.partition(":")
    if not separator:
        raise ValueError("Redis key is missing its logical resource key")
    return validate_tenant_id(tenant_id), _validate_resource_key(logical_key)


def namespaced_collection(collection: str) -> str:
    """Prefix a Qdrant collection with the deployment environment."""
    normalized = re.sub(r"[^a-zA-Z0-9_-]", "_", collection)
    return f"{settings.ENVIRONMENT}_{normalized}"


def tenant_storage_path(root: str | Path, object_name: str) -> Path:
    """Return a local storage path within the active tenant prefix."""
    if not object_name or Path(object_name).name != object_name or object_name in {".", ".."}:
        raise ValueError("object_name must be a single safe path segment")
    return Path(root).joinpath(*TenantNamespace.current().storage_prefix().split("/"), object_name)
