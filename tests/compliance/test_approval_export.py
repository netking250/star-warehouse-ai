"""Targeted exact-operation approval and sensitive export tests."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import select

import app.services.compliance_service as compliance_module
from app.authorization.policy import AuthenticatedPrincipal, AuthorizationContext, Role, Scope
from app.core.tenancy import TenantContext, TenantStatus
from app.models.compliance import (
    ApprovalRequest,
    ApprovalStatus,
    ComplianceAuditEvent,
    SensitiveExportArtifact,
)
from app.models.evaluation import MessageFeedback
from app.models.user import User
from app.observability.metrics import APPROVAL_REQUESTS_TOTAL, SENSITIVE_EXPORTS_TOTAL
from app.services.compliance_service import (
    ApprovalDeniedError,
    ApprovalNotFoundError,
    ApprovalSelfDecisionError,
    ComplianceService,
)


def _context(tenant_id: str, user_id: int, role: Role, scopes: set[str]) -> AuthorizationContext:
    return AuthorizationContext(
        principal=AuthenticatedPrincipal(
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=f"session-{user_id}",
            correlation_id=f"correlation-{user_id}",
            token_id=f"token-{user_id}",
        ),
        tenant=TenantContext(tenant_id, tenant_id, "Test tenant", TenantStatus.ACTIVE),
        roles=frozenset({role}),
        scopes=frozenset(scopes),
    )


async def _user(session, tenant_id: str, suffix: str, role: Role) -> User:
    user = User(
        tenant_id=tenant_id,
        username=f"approval-{suffix}",
        password_hash=User.hash_password("test-password"),
        email=f"approval-{suffix}@example.com",
        full_name="Approval Test User",
        role=role.value,
    )
    session.add(user)
    await session.flush()
    assert user.id is not None
    return user


@pytest.mark.asyncio
async def test_sensitive_export_requires_separate_exact_approval_and_is_idempotent(
    db_session, tenant_context: str
) -> None:
    now = datetime(2026, 9, 14, tzinfo=UTC)
    requester = await _user(db_session, tenant_context, "requester", Role.ANALYST)
    approver = await _user(db_session, tenant_context, "approver", Role.AUDITOR)
    assert requester.id is not None and approver.id is not None
    request_context = _context(
        tenant_context, requester.id, Role.ANALYST, {Scope.EXPORTS_REQUEST.value}
    )
    approve_context = _context(
        tenant_context, approver.id, Role.AUDITOR, {Scope.EXPORTS_APPROVE.value}
    )
    db_session.add(
        MessageFeedback(
            user_id=requester.id,
            thread_id="thread-approved",
            message_index=0,
            score=1,
            comment="private feedback",
            created_at=now,
        )
    )
    service = ComplianceService()
    parameters: dict[str, object] = {"category": "delivery"}
    requested_before = APPROVAL_REQUESTS_TOTAL.labels(
        operation="feedback_export", result="requested"
    )._value.get()
    approved_before = APPROVAL_REQUESTS_TOTAL.labels(
        operation="feedback_export", result="approved"
    )._value.get()
    exported_before = SENSITIVE_EXPORTS_TOTAL.labels(result="success")._value.get()

    approval = await service.request_feedback_export(
        db_session, actor=request_context, parameters=parameters, now=now
    )
    assert approval.status is ApprovalStatus.PENDING
    with pytest.raises(ApprovalSelfDecisionError):
        await service.decide(
            db_session, actor=request_context, approval_id=approval.id, approve=True, now=now
        )
    await service.decide(
        db_session, actor=approve_context, approval_id=approval.id, approve=True, now=now
    )
    assert approval.status is ApprovalStatus.APPROVED

    revoked_context = _context(tenant_context, requester.id, Role.ANALYST, set())
    with pytest.raises(ApprovalDeniedError, match="Current authorization"):
        await service.execute_feedback_export(
            db_session,
            actor=revoked_context,
            approval_id=approval.id,
            parameters=parameters,
            now=now,
        )

    with pytest.raises(ApprovalDeniedError):
        await service.execute_feedback_export(
            db_session,
            actor=request_context,
            approval_id=approval.id,
            parameters={"category": "different"},
            now=now,
        )

    first = await service.execute_feedback_export(
        db_session, actor=request_context, approval_id=approval.id, parameters=parameters, now=now
    )
    second = await service.execute_feedback_export(
        db_session,
        actor=request_context,
        approval_id=approval.id,
        parameters=parameters,
        now=now + timedelta(seconds=1),
    )
    assert first.id == second.id
    assert approval.status is ApprovalStatus.EXECUTED
    assert len((await db_session.exec(select(SensitiveExportArtifact))).all()) == 1
    assert (
        APPROVAL_REQUESTS_TOTAL.labels(operation="feedback_export", result="requested")._value.get()
        == requested_before + 1
    )
    assert (
        APPROVAL_REQUESTS_TOTAL.labels(operation="feedback_export", result="approved")._value.get()
        == approved_before + 1
    )
    assert SENSITIVE_EXPORTS_TOTAL.labels(result="success")._value.get() == exported_before + 1
    audits = (await db_session.exec(select(ComplianceAuditEvent))).all()
    assert all("private feedback" not in str(event.event_metadata) for event in audits)


@pytest.mark.asyncio
async def test_rejected_expired_and_cross_tenant_approvals_are_denied(
    db_session, tenant_context: str
) -> None:
    now = datetime(2026, 9, 14, tzinfo=UTC)
    requester = await _user(db_session, tenant_context, "denied-requester", Role.ANALYST)
    approver = await _user(db_session, tenant_context, "denied-approver", Role.AUDITOR)
    assert requester.id is not None and approver.id is not None
    request_context = _context(
        tenant_context, requester.id, Role.ANALYST, {Scope.EXPORTS_REQUEST.value}
    )
    approve_context = _context(
        tenant_context, approver.id, Role.AUDITOR, {Scope.EXPORTS_APPROVE.value}
    )
    service = ComplianceService()

    rejected = await service.request_feedback_export(
        db_session, actor=request_context, parameters={}, now=now
    )
    await service.decide(
        db_session, actor=approve_context, approval_id=rejected.id, approve=False, now=now
    )
    with pytest.raises(ApprovalDeniedError):
        await service.execute_feedback_export(
            db_session, actor=request_context, approval_id=rejected.id, parameters={}, now=now
        )

    expired = await service.request_feedback_export(
        db_session, actor=request_context, parameters={}, now=now
    )
    with pytest.raises(ApprovalDeniedError):
        await service.decide(
            db_session,
            actor=approve_context,
            approval_id=expired.id,
            approve=True,
            now=now + timedelta(minutes=16),
        )
    assert ApprovalStatus(expired.status) is ApprovalStatus.EXPIRED

    other_context = _context(
        "other-tenant", requester.id, Role.ANALYST, {Scope.EXPORTS_REQUEST.value}
    )
    with pytest.raises(ApprovalNotFoundError, match="Approval request not found"):
        await service.execute_feedback_export(
            db_session, actor=other_context, approval_id=rejected.id, parameters={}, now=now
        )


@pytest.mark.asyncio
async def test_approval_and_audit_rollback_together(db_session, tenant_context: str) -> None:
    now = datetime(2026, 9, 14, tzinfo=UTC)
    requester = await _user(db_session, tenant_context, "rollback-requester", Role.ANALYST)
    assert requester.id is not None
    context = _context(tenant_context, requester.id, Role.ANALYST, {Scope.EXPORTS_REQUEST.value})

    await ComplianceService().request_feedback_export(
        db_session, actor=context, parameters={}, now=now
    )
    await db_session.rollback()

    assert not (await db_session.exec(select(ComplianceAuditEvent))).all()


@pytest.mark.asyncio
async def test_approval_decision_and_audit_failure_roll_back_atomically(
    db_session, tenant_context: str, monkeypatch
) -> None:
    now = datetime(2026, 9, 14, tzinfo=UTC)
    requester = await _user(db_session, tenant_context, "atomic-requester", Role.ANALYST)
    approver = await _user(db_session, tenant_context, "atomic-approver", Role.AUDITOR)
    assert requester.id is not None and approver.id is not None
    request_context = _context(
        tenant_context, requester.id, Role.ANALYST, {Scope.EXPORTS_REQUEST.value}
    )
    approve_context = _context(
        tenant_context, approver.id, Role.AUDITOR, {Scope.EXPORTS_APPROVE.value}
    )
    service = ComplianceService()
    approval = await service.request_feedback_export(
        db_session, actor=request_context, parameters={}, now=now
    )
    await db_session.commit()
    approval_id = approval.id
    assert approval_id is not None

    async def fail_audit(*args: object, **kwargs: object) -> None:
        raise RuntimeError("forced audit failure")

    monkeypatch.setattr(compliance_module, "append_compliance_audit", fail_audit)
    decision_savepoint = await db_session.begin_nested()
    with pytest.raises(RuntimeError, match="forced audit failure"):
        await service.decide(
            db_session,
            actor=approve_context,
            approval_id=approval_id,
            approve=True,
            now=now,
        )
    await decision_savepoint.rollback()

    persisted = await db_session.get(ApprovalRequest, approval_id)
    assert persisted is not None
    assert ApprovalStatus(persisted.status) is ApprovalStatus.PENDING
    audit_types = {
        event.event_type for event in (await db_session.exec(select(ComplianceAuditEvent))).all()
    }
    assert "sensitive_export.approved" not in audit_types


@pytest.mark.asyncio
async def test_export_generation_failure_is_audited_and_counted(
    db_session, tenant_context: str, monkeypatch
) -> None:
    now = datetime(2026, 9, 14, tzinfo=UTC)
    requester = await _user(db_session, tenant_context, "failure-requester", Role.ANALYST)
    approver = await _user(db_session, tenant_context, "failure-approver", Role.AUDITOR)
    assert requester.id is not None and approver.id is not None
    request_context = _context(
        tenant_context, requester.id, Role.ANALYST, {Scope.EXPORTS_REQUEST.value}
    )
    approve_context = _context(
        tenant_context, approver.id, Role.AUDITOR, {Scope.EXPORTS_APPROVE.value}
    )
    service = ComplianceService()
    approval = await service.request_feedback_export(
        db_session, actor=request_context, parameters={}, now=now
    )
    await service.decide(
        db_session, actor=approve_context, approval_id=approval.id, approve=True, now=now
    )
    failures_before = SENSITIVE_EXPORTS_TOTAL.labels(result="failure")._value.get()

    async def fail_rows(
        session: object, parameters: dict[str, object], *, tenant_id: str
    ) -> list[MessageFeedback]:
        del session, parameters, tenant_id
        raise RuntimeError("synthetic export failure")

    monkeypatch.setattr(ComplianceService, "_feedback_rows", staticmethod(fail_rows))
    with pytest.raises(RuntimeError, match="Sensitive export generation failed"):
        await service.execute_feedback_export(
            db_session, actor=request_context, approval_id=approval.id, parameters={}, now=now
        )

    assert SENSITIVE_EXPORTS_TOTAL.labels(result="failure")._value.get() == failures_before + 1
    events = (await db_session.exec(select(ComplianceAuditEvent))).all()
    failed = [event for event in events if event.event_type == "sensitive_export.execution_failed"]
    assert len(failed) == 1
    assert failed[0].event_metadata == {"error_type": "RuntimeError"}
