"""Bounded tenant-aware retention planning and execution."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from time import monotonic

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.compliance.audit import append_compliance_audit
from app.compliance.classification import DATASET_POLICIES, DeletionStrategy
from app.core.config import settings
from app.models.compliance import SensitiveExportArtifact
from app.models.evaluation import MessageFeedback
from app.models.knowledge_document import KnowledgeDocument
from app.models.message import MessageCard
from app.observability.metrics import (
    RETENTION_RECORDS_PROCESSED_TOTAL,
    RETENTION_RUN_DURATION_SECONDS,
    RETENTION_RUNS_TOTAL,
)
from app.services.knowledge_service import delete_knowledge_assets

logger = logging.getLogger(__name__)


class RetentionPolicyError(Exception):
    """Raised when a dataset cannot be processed by the retention engine."""


class RetentionExecutionDisabledError(Exception):
    """Raised when destructive retention is stopped by configuration."""


@dataclass(frozen=True, slots=True)
class RetentionResult:
    """Inspectable result for a bounded retention plan or execution."""

    dataset: str
    tenant_id: str
    dry_run: bool
    eligible_count: int
    processed_count: int
    failed_count: int
    record_ids: tuple[str, ...]


_RETENTION_MODELS = {
    "message_cards": (MessageCard, MessageCard.created_at),
    "message_feedbacks": (MessageFeedback, MessageFeedback.created_at),
    "knowledge_documents": (KnowledgeDocument, KnowledgeDocument.created_at),
    "sensitive_export_artifacts": (SensitiveExportArtifact, SensitiveExportArtifact.expires_at),
}

EXECUTABLE_RETENTION_DATASETS = tuple(sorted(_RETENTION_MODELS))


class RetentionExecutor:
    """Plan and execute one explicit, predicate-bound retention batch."""

    async def run(
        self,
        session: AsyncSession,
        *,
        dataset: str,
        tenant_id: str,
        now: datetime,
        dry_run: bool,
        correlation_id: str,
        actor_user_id: int | None,
        batch_limit: int | None = None,
    ) -> RetentionResult:
        """Process a bounded tenant batch; the caller owns commit or rollback."""
        started = monotonic()
        policy = DATASET_POLICIES.get(dataset)
        if policy is None or not policy.retention_enabled or policy.retention_days is None:
            raise RetentionPolicyError("Dataset has no enabled retention policy")
        model_entry = _RETENTION_MODELS.get(dataset)
        if model_entry is None:
            raise RetentionPolicyError("Dataset retention strategy is not implemented")
        if policy.deletion_strategy not in {
            DeletionStrategy.HARD_DELETE,
            DeletionStrategy.DELETE_EXTERNAL_OBJECT,
        }:
            raise RetentionPolicyError("Dataset retention strategy is not executable")
        requested_limit = policy.batch_limit if batch_limit is None else batch_limit
        limit = min(requested_limit, policy.batch_limit, settings.RETENTION_BATCH_LIMIT)
        if limit < 1:
            raise RetentionPolicyError("Retention batch limit must be positive")
        if not dry_run and not settings.RETENTION_EXECUTION_ENABLED:
            RETENTION_RUNS_TOTAL.labels(result="disabled").inc()
            raise RetentionExecutionDisabledError("Retention execution is disabled")

        model, timestamp_column = model_entry
        cutoff = now - timedelta(days=policy.retention_days)
        statement = (
            select(model)
            .where(model.tenant_id == tenant_id, timestamp_column < cutoff)
            .order_by(col(timestamp_column), col(model.id))
            .limit(limit)
        )
        try:
            records = list((await session.exec(statement)).all())
            ids = tuple(str(record.id) for record in records)
            if dry_run:
                RETENTION_RUNS_TOTAL.labels(result="dry_run").inc()
                return RetentionResult(dataset, tenant_id, True, len(records), 0, 0, ids)

            processed = 0
            for record in records:
                if policy.deletion_strategy is DeletionStrategy.DELETE_EXTERNAL_OBJECT:
                    await self._delete_knowledge_object(record, tenant_id=tenant_id)
                await session.delete(record)
                processed += 1
            await append_compliance_audit(
                session,
                event_type="retention.execution.completed",
                actor_user_id=actor_user_id,
                actor_type="USER" if actor_user_id is not None else "SYSTEM",
                target_type=dataset,
                target_reference=None,
                outcome="SUCCEEDED",
                reason_code="RETENTION_POLICY_ELIGIBLE",
                correlation_id=correlation_id,
                metadata={"record_count": processed, "dry_run": False},
            )
            RETENTION_RUNS_TOTAL.labels(result="success").inc()
            RETENTION_RECORDS_PROCESSED_TOTAL.labels(dataset=dataset, result="success").inc(
                processed
            )
            return RetentionResult(dataset, tenant_id, False, len(records), processed, 0, ids)
        except Exception:
            RETENTION_RUNS_TOTAL.labels(result="failure").inc()
            RETENTION_RECORDS_PROCESSED_TOTAL.labels(dataset=dataset, result="failure").inc()
            logger.exception(
                "Retention execution failed", extra={"dataset": dataset, "tenant_id": tenant_id}
            )
            raise
        finally:
            RETENTION_RUN_DURATION_SECONDS.observe(monotonic() - started)

    @staticmethod
    async def _delete_knowledge_object(record: object, *, tenant_id: str) -> None:
        if not isinstance(record, KnowledgeDocument):
            raise RetentionPolicyError("External-object strategy requires a knowledge document")
        if record.id is None:
            raise RetentionPolicyError("Knowledge document must be persisted before deletion")
        await delete_knowledge_assets(
            tenant_id=tenant_id,
            document_id=record.id,
            object_key=record.storage_path,
        )
