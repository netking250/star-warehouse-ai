"""Transactional approval and sensitive feedback-export application service."""

import csv
import io
import logging
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.authorization.policy import AuthorizationContext
from app.compliance.approval import (
    FEEDBACK_EXPORT,
    canonical_operation_parameters,
    operation_hash,
)
from app.compliance.audit import append_compliance_audit
from app.models.compliance import ApprovalRequest, ApprovalStatus, SensitiveExportArtifact
from app.models.evaluation import MessageFeedback
from app.observability.metrics import (
    APPROVAL_PENDING,
    APPROVAL_REQUESTS_TOTAL,
    SENSITIVE_EXPORTS_TOTAL,
)

logger = logging.getLogger(__name__)


class ApprovalError(Exception):
    """Base class for stable sensitive-operation approval failures."""


class ApprovalNotFoundError(ApprovalError):
    """Raised when an approval is absent from the current tenant."""


class ApprovalDeniedError(ApprovalError):
    """Raised when approval state or operation binding denies execution."""


class ApprovalExpiredError(ApprovalDeniedError):
    """Raised when an approval is expired and its terminal state is recorded."""


class ExportGenerationError(RuntimeError):
    """Raised after a generation failure has staged sanitized failure evidence."""


class ApprovalSelfDecisionError(ApprovalError):
    """Raised when a requester attempts to approve their own export."""


class ComplianceService:
    """Own exact-operation approval and synchronous idempotent export transactions."""

    async def request_feedback_export(
        self,
        session: AsyncSession,
        *,
        actor: AuthorizationContext,
        parameters: dict[str, object],
        now: datetime,
    ) -> ApprovalRequest:
        """Stage a pending approval and request audit atomically."""
        if not actor.has_scope(FEEDBACK_EXPORT.request_scope):
            raise ApprovalDeniedError("Current authorization cannot request sensitive exports")
        normalized = canonical_operation_parameters(parameters)
        approval = ApprovalRequest(
            operation_type=FEEDBACK_EXPORT.operation_type,
            requester_user_id=actor.user_id,
            operation_payload_hash=operation_hash(
                tenant_id=actor.tenant_id,
                operation_type=FEEDBACK_EXPORT.operation_type,
                requester_user_id=actor.user_id,
                parameters=normalized,
            ),
            operation_parameters=normalized,
            requested_at=now,
            expires_at=now + timedelta(seconds=FEEDBACK_EXPORT.ttl_seconds),
            correlation_id=actor.correlation_id,
        )
        session.add(approval)
        await append_compliance_audit(
            session,
            event_type="sensitive_export.requested",
            actor_user_id=actor.user_id,
            actor_type="USER",
            target_type="feedback_export",
            target_reference=approval.id,
            outcome="PENDING",
            reason_code="APPROVAL_REQUIRED",
            correlation_id=actor.correlation_id,
            metadata={"operation_hash": approval.operation_payload_hash},
        )
        APPROVAL_REQUESTS_TOTAL.labels(operation="feedback_export", result="requested").inc()
        APPROVAL_PENDING.inc()
        return approval

    async def decide(
        self,
        session: AsyncSession,
        *,
        actor: AuthorizationContext,
        approval_id: str,
        approve: bool,
        now: datetime,
    ) -> ApprovalRequest:
        """Approve or reject one current-tenant request with atomic audit evidence."""
        approval = await self._approval(session, approval_id, actor.tenant_id, lock=True)
        if approval.operation_type != FEEDBACK_EXPORT.operation_type:
            raise ApprovalDeniedError("Unsupported sensitive operation")
        if approval.requester_user_id == actor.user_id:
            raise ApprovalSelfDecisionError("Requester cannot decide their own sensitive export")
        if not actor.has_scope(FEEDBACK_EXPORT.approval_scope):
            raise ApprovalDeniedError("Current authorization cannot decide sensitive exports")
        if ApprovalStatus(approval.status) is not ApprovalStatus.PENDING:
            raise ApprovalDeniedError("Approval is not pending")
        if now >= approval.expires_at:
            approval.status = ApprovalStatus.EXPIRED
            approval.decision_at = now
            session.add(approval)
            await append_compliance_audit(
                session,
                event_type="sensitive_export.expired",
                actor_user_id=actor.user_id,
                actor_type="USER",
                target_type="feedback_export",
                target_reference=approval.id,
                outcome=ApprovalStatus.EXPIRED.value,
                reason_code="APPROVAL_EXPIRED",
                correlation_id=actor.correlation_id,
                metadata={"operation_hash": approval.operation_payload_hash},
            )
            APPROVAL_REQUESTS_TOTAL.labels(operation="feedback_export", result="expired").inc()
            APPROVAL_PENDING.dec()
            await session.flush()
            raise ApprovalExpiredError("Approval has expired")
        approval.status = ApprovalStatus.APPROVED if approve else ApprovalStatus.REJECTED
        approval.approver_user_id = actor.user_id
        approval.decision_at = now
        session.add(approval)
        await append_compliance_audit(
            session,
            event_type="sensitive_export.approved" if approve else "sensitive_export.rejected",
            actor_user_id=actor.user_id,
            actor_type="USER",
            target_type="feedback_export",
            target_reference=approval.id,
            outcome=approval.status.value,
            reason_code="AUTHORIZED_DECISION",
            correlation_id=actor.correlation_id,
            metadata={"operation_hash": approval.operation_payload_hash},
        )
        APPROVAL_REQUESTS_TOTAL.labels(
            operation="feedback_export", result="approved" if approve else "rejected"
        ).inc()
        APPROVAL_PENDING.dec()
        await session.flush()
        return approval

    async def execute_feedback_export(
        self,
        session: AsyncSession,
        *,
        actor: AuthorizationContext,
        approval_id: str,
        parameters: dict[str, object],
        now: datetime,
    ) -> SensitiveExportArtifact:
        """Generate or return the one artifact bound to an approved operation."""
        if not actor.has_scope(FEEDBACK_EXPORT.request_scope):
            raise ApprovalDeniedError("Current authorization cannot execute sensitive exports")
        approval = await self._approval(session, approval_id, actor.tenant_id, lock=True)
        if approval.operation_type != FEEDBACK_EXPORT.operation_type:
            raise ApprovalDeniedError("Unsupported sensitive operation")
        if approval.requester_user_id != actor.user_id:
            raise ApprovalDeniedError("Approval belongs to a different requester")
        normalized = canonical_operation_parameters(parameters)
        expected_hash = operation_hash(
            tenant_id=actor.tenant_id,
            operation_type=FEEDBACK_EXPORT.operation_type,
            requester_user_id=actor.user_id,
            parameters=normalized,
        )
        if expected_hash != approval.operation_payload_hash:
            raise ApprovalDeniedError("Export parameters do not match the approved operation")
        existing = (
            await session.exec(
                select(SensitiveExportArtifact).where(
                    SensitiveExportArtifact.approval_request_id == approval.id,
                    SensitiveExportArtifact.tenant_id == actor.tenant_id,
                )
            )
        ).one_or_none()
        if (
            existing is not None
            and existing.operation_payload_hash != approval.operation_payload_hash
        ):
            raise ApprovalDeniedError("Export artifact does not match the approved operation")
        approval_status = ApprovalStatus(approval.status)
        if approval_status is ApprovalStatus.EXECUTED and existing is not None:
            if now >= existing.expires_at:
                raise ApprovalDeniedError("Sensitive export artifact has expired")
            return existing
        if approval_status is not ApprovalStatus.APPROVED:
            raise ApprovalDeniedError("Sensitive export is not approved")
        if now >= approval.expires_at:
            approval.status = ApprovalStatus.EXPIRED
            approval.decision_at = now
            session.add(approval)
            await append_compliance_audit(
                session,
                event_type="sensitive_export.expired",
                actor_user_id=actor.user_id,
                actor_type="USER",
                target_type="feedback_export",
                target_reference=approval.id,
                outcome=ApprovalStatus.EXPIRED.value,
                reason_code="APPROVAL_EXPIRED",
                correlation_id=actor.correlation_id,
                metadata={"operation_hash": approval.operation_payload_hash},
            )
            APPROVAL_REQUESTS_TOTAL.labels(operation="feedback_export", result="expired").inc()
            await session.flush()
            raise ApprovalExpiredError("Approval has expired")

        await append_compliance_audit(
            session,
            event_type="sensitive_export.execution_started",
            actor_user_id=actor.user_id,
            actor_type="USER",
            target_type="feedback_export",
            target_reference=approval.id,
            outcome="STARTED",
            reason_code="APPROVAL_VALID",
            correlation_id=actor.correlation_id,
            metadata={"operation_hash": approval.operation_payload_hash},
        )
        try:
            items = await self._feedback_rows(session, normalized, tenant_id=actor.tenant_id)
            content = self._feedback_csv(items)
        except Exception as error:
            SENSITIVE_EXPORTS_TOTAL.labels(result="failure").inc()
            try:
                await append_compliance_audit(
                    session,
                    event_type="sensitive_export.execution_failed",
                    actor_user_id=actor.user_id,
                    actor_type="USER",
                    target_type="feedback_export",
                    target_reference=approval.id,
                    outcome="FAILED",
                    reason_code="EXPORT_GENERATION_FAILED",
                    correlation_id=actor.correlation_id,
                    metadata={"error_type": type(error).__name__},
                )
            except Exception:
                logger.exception(
                    "Sensitive export failure audit could not be staged",
                    extra={"operation": "feedback_export", "tenant_id": actor.tenant_id},
                )
            raise ExportGenerationError("Sensitive export generation failed") from None
        artifact = SensitiveExportArtifact(
            approval_request_id=approval.id,
            operation_payload_hash=approval.operation_payload_hash,
            filename=f"feedback_export_{now.strftime('%Y%m%dT%H%M%SZ')}.csv",
            content=content,
            record_count=len(items),
            created_at=now,
            expires_at=now + timedelta(minutes=15),
        )
        session.add(artifact)
        approval.status = ApprovalStatus.EXECUTED
        approval.executed_at = now
        session.add(approval)
        await append_compliance_audit(
            session,
            event_type="sensitive_export.execution_succeeded",
            actor_user_id=actor.user_id,
            actor_type="USER",
            target_type="feedback_export",
            target_reference=approval.id,
            outcome="SUCCEEDED",
            reason_code="ARTIFACT_CREATED",
            correlation_id=actor.correlation_id,
            metadata={
                "record_count": len(items),
                "operation_hash": approval.operation_payload_hash,
            },
        )
        await session.flush()
        SENSITIVE_EXPORTS_TOTAL.labels(result="success").inc()
        return artifact

    async def list_approvals(
        self, session: AsyncSession, *, tenant_id: str
    ) -> list[ApprovalRequest]:
        """List current-tenant approval requests without exported contents."""
        return list(
            (
                await session.exec(
                    select(ApprovalRequest)
                    .where(ApprovalRequest.tenant_id == tenant_id)
                    .order_by(col(ApprovalRequest.requested_at).desc())
                    .limit(100)
                )
            ).all()
        )

    @staticmethod
    async def _approval(
        session: AsyncSession, approval_id: str, tenant_id: str, *, lock: bool
    ) -> ApprovalRequest:
        statement = select(ApprovalRequest).where(
            ApprovalRequest.id == approval_id, ApprovalRequest.tenant_id == tenant_id
        )
        if lock:
            statement = statement.with_for_update()
        approval = (await session.exec(statement)).one_or_none()
        if approval is None:
            raise ApprovalNotFoundError("Approval request not found")
        return approval

    @staticmethod
    async def _feedback_rows(
        session: AsyncSession, parameters: dict[str, object], *, tenant_id: str
    ) -> list[MessageFeedback]:
        statement = (
            select(MessageFeedback)
            .where(MessageFeedback.tenant_id == tenant_id)
            .order_by(col(MessageFeedback.created_at).desc())
            .limit(10000)
        )
        date_from = parameters.get("date_from")
        date_to = parameters.get("date_to")
        if isinstance(date_from, str):
            statement = statement.where(
                MessageFeedback.created_at >= datetime.fromisoformat(date_from)
            )
        if isinstance(date_to, str):
            statement = statement.where(
                MessageFeedback.created_at <= datetime.fromisoformat(date_to)
            )
        for key, column in (
            ("agent_type", MessageFeedback.agent_type),
            ("category", MessageFeedback.category),
        ):
            value = parameters.get(key)
            if isinstance(value, str):
                statement = statement.where(column == value)
        search = parameters.get("search")
        if isinstance(search, str) and search:
            search_pattern = f"%{search}%"
            statement = statement.where(
                func.lower(MessageFeedback.comment).like(func.lower(search_pattern))
            )
        sentiment = parameters.get("sentiment")
        if isinstance(sentiment, str):
            score = {"up": 1, "neutral": 0, "down": -1}.get(sentiment)
            if score is not None:
                statement = statement.where(MessageFeedback.score == score)
        return list((await session.exec(statement)).all())

    @staticmethod
    def _feedback_csv(items: list[MessageFeedback]) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "user_id",
                "thread_id",
                "message_index",
                "score",
                "comment",
                "category",
                "agent_type",
                "confidence_score",
                "created_at",
            ]
        )
        for item in items:
            writer.writerow(
                [
                    item.id,
                    item.user_id,
                    item.thread_id,
                    item.message_index,
                    item.score,
                    item.comment,
                    item.category,
                    item.agent_type,
                    item.confidence_score,
                    item.created_at.isoformat(),
                ]
            )
        return output.getvalue()
