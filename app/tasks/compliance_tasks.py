"""Scheduled bounded compliance retention on the maintenance worker."""

import logging
from typing import TypedDict

from asgiref.sync import async_to_sync
from sqlmodel import col, select

from app.celery_app import celery_app
from app.compliance.retention import EXECUTABLE_RETENTION_DATASETS, RetentionExecutor
from app.core.config import settings
from app.core.database import async_session_maker
from app.core.tenancy import tenant_scope
from app.core.utils import utc_now
from app.models.tenant import Tenant
from app.task_runtime.system import system_task_handler

logger = logging.getLogger(__name__)


class ScheduledRetentionResult(TypedDict):
    """Low-detail operational result returned by the scheduled task."""

    status: str
    tenants: int
    processed: int
    failures: int


async def _run_scheduled_retention() -> ScheduledRetentionResult:
    if settings.DB_CAPABILITY != "maintenance":
        raise RuntimeError("Scheduled retention requires the explicit maintenance DB capability")
    now = utc_now()
    async with async_session_maker() as session:
        tenants = list(
            (
                await session.exec(
                    select(Tenant)
                    .order_by(col(Tenant.id))
                    .limit(settings.RETENTION_TENANT_BATCH_LIMIT)
                )
            ).all()
        )

    processed = 0
    failures = 0
    for tenant in tenants:
        for dataset in EXECUTABLE_RETENTION_DATASETS:
            try:
                with tenant_scope(tenant.id):
                    async with async_session_maker() as session, session.begin():
                        result = await RetentionExecutor().run(
                            session,
                            dataset=dataset,
                            tenant_id=tenant.id,
                            now=now,
                            dry_run=False,
                            correlation_id=f"scheduled-retention:{now.date().isoformat()}",
                            actor_user_id=None,
                        )
                        processed += result.processed_count
            except Exception:
                failures += 1
                logger.exception(
                    "Scheduled retention batch failed",
                    extra={"dataset": dataset, "tenant_id": tenant.id},
                )
    return {
        "status": "failed" if failures else "success",
        "tenants": len(tenants),
        "processed": processed,
        "failures": failures,
    }


@celery_app.task(name="compliance.run_retention_daily")
@system_task_handler("compliance.run_retention_daily")
def run_retention_daily() -> ScheduledRetentionResult:
    """Run the scheduled bounded retention pass on the maintenance worker."""
    return async_to_sync(_run_scheduled_retention)()
