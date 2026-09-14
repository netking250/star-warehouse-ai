"""PostgreSQL row-level-security runtime primitives."""

from __future__ import annotations

import logging
from enum import StrEnum

from sqlalchemy import text
from sqlalchemy.engine import Connection

DATABASE_TENANT_SETTING = "app.current_tenant_id"
RUNTIME_CAPABILITY_ROLE = "star_warehouse_runtime"
MAINTENANCE_CAPABILITY_ROLE = "star_warehouse_maintenance"

logger = logging.getLogger(__name__)


class DatabaseCapability(StrEnum):
    """Database capabilities assigned to independently deployed runtime roles."""

    RUNTIME = "runtime"
    MAINTENANCE = "maintenance"


class DatabaseTenantBindingError(RuntimeError):
    """Raised when PostgreSQL tenant context cannot be bound safely."""


def capability_role(capability: DatabaseCapability | str) -> str:
    """Return the fixed PostgreSQL role for a configured database capability."""
    selected = DatabaseCapability(capability)
    if selected is DatabaseCapability.MAINTENANCE:
        return MAINTENANCE_CAPABILITY_ROLE
    return RUNTIME_CAPABILITY_ROLE


def bind_database_transaction(
    connection: Connection,
    *,
    capability: DatabaseCapability | str,
    tenant_id: str | None,
) -> None:
    """Apply the effective role and transaction-local tenant setting.

    SQLite and other non-PostgreSQL test engines are intentionally unaffected.
    PostgreSQL receives an explicit empty value when no tenant is bound so a
    pooled connection cannot inherit a prior transaction's tenant identity.

    Args:
        connection: SQLAlchemy connection for the active transaction.
        capability: Least-privilege runtime or maintenance capability.
        tenant_id: Trusted tenant identity, or ``None`` for an explicit global operation.

    Raises:
        DatabaseTenantBindingError: If role or tenant binding fails.
    """
    if connection.dialect.name != "postgresql":
        return

    role = capability_role(capability)
    try:
        connection.exec_driver_sql(f'SET LOCAL ROLE "{role}"')
        connection.execute(
            text("SELECT set_config(:setting_name, :tenant_id, true)"),
            {"setting_name": DATABASE_TENANT_SETTING, "tenant_id": tenant_id or ""},
        )
    except Exception as error:
        logger.exception(
            "PostgreSQL tenant context binding failed",
            extra={
                "event": "database_tenant_binding_failed",
                "tenant_id": tenant_id or "<missing>",
                "operation": "bind_transaction_context",
                "resource_type": "postgresql",
                "database_capability": str(capability),
            },
        )
        raise DatabaseTenantBindingError("PostgreSQL tenant context binding failed") from error
