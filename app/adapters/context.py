"""Adapter context construction helpers."""

from app.adapters.contracts import AdapterContext
from app.core.logging import get_correlation_id
from app.core.tenancy import get_current_tenant_id


def current_adapter_context(user_id: int) -> AdapterContext:
    """Build the upstream context from trusted request-scoped state."""
    return AdapterContext(
        tenant_id=get_current_tenant_id(),
        user_id=user_id,
        correlation_id=get_correlation_id(),
    )
