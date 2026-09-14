"""Minimal sanitized append-only compliance audit writer."""

from collections.abc import Mapping

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.compliance import ComplianceAuditEvent
from app.observability.metrics import AUDIT_WRITE_FAILURES_TOTAL

_SENSITIVE_KEYS = frozenset(
    {"password", "secret", "token", "jwt", "cookie", "csrf", "authorization", "content"}
)


def sanitize_audit_metadata(metadata: Mapping[str, object] | None) -> dict[str, object]:
    """Keep low-risk scalar metadata and redact credential-like fields."""
    sanitized: dict[str, object] = {}
    for key, value in (metadata or {}).items():
        lowered = key.lower()
        if any(marker in lowered for marker in _SENSITIVE_KEYS):
            sanitized[key] = "[REDACTED]"
        elif isinstance(value, (str, int, float, bool)) or value is None:
            sanitized[key] = value[:256] if isinstance(value, str) else value
    return sanitized


async def append_compliance_audit(
    session: AsyncSession,
    *,
    event_type: str,
    actor_user_id: int | None,
    actor_type: str,
    target_type: str,
    target_reference: str | None,
    outcome: str,
    reason_code: str,
    correlation_id: str,
    metadata: Mapping[str, object] | None = None,
) -> ComplianceAuditEvent:
    """Stage append-only compliance evidence in the caller-owned transaction."""
    event = ComplianceAuditEvent(
        event_type=event_type,
        actor_user_id=actor_user_id,
        actor_type=actor_type,
        target_type=target_type,
        target_reference=target_reference,
        outcome=outcome,
        reason_code=reason_code,
        correlation_id=correlation_id,
        event_metadata=sanitize_audit_metadata(metadata),
    )
    session.add(event)
    try:
        await session.flush()
    except Exception:
        AUDIT_WRITE_FAILURES_TOTAL.inc()
        raise
    return event
