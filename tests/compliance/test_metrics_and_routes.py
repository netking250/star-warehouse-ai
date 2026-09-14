"""Compliance metric-cardinality and route-inventory guards."""

import pytest

from app.authorization.route_inventory import (
    HTTP_ROUTE_POLICIES,
    RouteClassification,
    inventory_routes,
)
from app.core.config import settings
from app.main import app
from app.observability import metrics
from app.tasks.compliance_tasks import _run_scheduled_retention


def test_compliance_metrics_use_only_low_cardinality_labels() -> None:
    collectors = (
        metrics.RETENTION_RUNS_TOTAL,
        metrics.RETENTION_RECORDS_PROCESSED_TOTAL,
        metrics.APPROVAL_REQUESTS_TOTAL,
        metrics.APPROVAL_PENDING,
        metrics.SENSITIVE_EXPORTS_TOTAL,
        metrics.AUDIT_WRITE_FAILURES_TOTAL,
    )
    forbidden = {"tenant_id", "user_id", "email", "resource_id"}

    assert all(not forbidden.intersection(collector._labelnames) for collector in collectors)


def test_compliance_routes_are_classified_and_never_public() -> None:
    _, unclassified = inventory_routes(app)
    sensitive = {
        key: policy
        for key, policy in HTTP_ROUTE_POLICIES.items()
        if "/compliance/" in key[1] or "feedback/export" in key[1]
    }

    assert not unclassified
    assert sensitive
    assert all(
        policy.classification is RouteClassification.TENANT_SCOPE_REQUIRED
        for policy in sensitive.values()
    )


@pytest.mark.asyncio
async def test_scheduled_retention_requires_maintenance_capability(monkeypatch) -> None:
    monkeypatch.setattr(settings, "DB_CAPABILITY", "runtime")

    with pytest.raises(RuntimeError, match="maintenance DB capability"):
        await _run_scheduled_retention()
