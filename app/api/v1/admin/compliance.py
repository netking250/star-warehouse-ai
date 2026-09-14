"""Minimal T09-authorized compliance lifecycle endpoints."""

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.authorization.policy import AuthorizationContext
from app.compliance.retention import (
    RetentionExecutionDisabledError,
    RetentionExecutor,
    RetentionPolicyError,
)
from app.core.database import get_session
from app.core.security import get_authorized_auth_context
from app.core.utils import utc_now
from app.schemas.compliance import (
    ApprovalDecisionRequest,
    ApprovalResponse,
    RetentionRunRequest,
    RetentionRunResponse,
)
from app.services.compliance_service import (
    ApprovalDeniedError,
    ApprovalExpiredError,
    ApprovalNotFoundError,
    ApprovalSelfDecisionError,
    ComplianceService,
)

router = APIRouter()


@router.get("/approvals", response_model=list[ApprovalResponse])
async def list_approvals(
    actor: AuthorizationContext = Depends(get_authorized_auth_context),
    session: AsyncSession = Depends(get_session),
    service: ComplianceService = Depends(ComplianceService),
) -> list[ApprovalResponse]:
    """List approval metadata inside the current tenant."""
    approvals = await service.list_approvals(session, tenant_id=actor.tenant_id)
    return [ApprovalResponse.model_validate(item) for item in approvals]


@router.post("/approvals/{approval_id}/decision", response_model=ApprovalResponse)
async def decide_approval(
    approval_id: str,
    body: ApprovalDecisionRequest,
    actor: AuthorizationContext = Depends(get_authorized_auth_context),
    session: AsyncSession = Depends(get_session),
    service: ComplianceService = Depends(ComplianceService),
) -> ApprovalResponse:
    """Approve or reject a sensitive export as a separate authorized actor."""
    try:
        approval = await service.decide(
            session,
            actor=actor,
            approval_id=approval_id,
            approve=body.decision == "APPROVE",
            now=utc_now(),
        )
        await session.commit()
        return ApprovalResponse.model_validate(approval)
    except ApprovalNotFoundError as error:
        await session.rollback()
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ApprovalExpiredError as error:
        await session.commit()
        raise HTTPException(status_code=409, detail=str(error)) from error
    except (ApprovalDeniedError, ApprovalSelfDecisionError) as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/retention/{dataset}/dry-run", response_model=RetentionRunResponse)
async def dry_run_retention(
    dataset: str,
    body: RetentionRunRequest,
    actor: AuthorizationContext = Depends(get_authorized_auth_context),
    session: AsyncSession = Depends(get_session),
    executor: RetentionExecutor = Depends(RetentionExecutor),
) -> RetentionRunResponse:
    """Inspect one bounded current-tenant retention batch without mutation."""
    try:
        result = await executor.run(
            session,
            dataset=dataset,
            tenant_id=actor.tenant_id,
            now=utc_now(),
            dry_run=True,
            correlation_id=actor.correlation_id,
            actor_user_id=actor.user_id,
            batch_limit=body.batch_limit,
        )
        return RetentionRunResponse(**asdict(result))
    except RetentionPolicyError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/retention/{dataset}/execute", response_model=RetentionRunResponse)
async def execute_retention(
    dataset: str,
    body: RetentionRunRequest,
    actor: AuthorizationContext = Depends(get_authorized_auth_context),
    session: AsyncSession = Depends(get_session),
    executor: RetentionExecutor = Depends(RetentionExecutor),
) -> RetentionRunResponse:
    """Execute one bounded current-tenant retention batch."""
    try:
        result = await executor.run(
            session,
            dataset=dataset,
            tenant_id=actor.tenant_id,
            now=utc_now(),
            dry_run=False,
            correlation_id=actor.correlation_id,
            actor_user_id=actor.user_id,
            batch_limit=body.batch_limit,
        )
        await session.commit()
        return RetentionRunResponse(**asdict(result))
    except RetentionExecutionDisabledError as error:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from error
    except RetentionPolicyError as error:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(error)) from error
