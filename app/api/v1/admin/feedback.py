import logging
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.authorization.policy import AuthorizationContext
from app.core.database import get_session
from app.core.security import get_admin_user_id, get_authorized_auth_context
from app.core.utils import utc_now
from app.observability.metrics import SENSITIVE_EXPORTS_TOTAL
from app.schemas.compliance import ApprovalResponse, FeedbackExportFilters, SensitiveExportResponse
from app.services.compliance_service import (
    ApprovalDeniedError,
    ApprovalExpiredError,
    ApprovalNotFoundError,
    ComplianceService,
    ExportGenerationError,
)
from app.services.online_eval import OnlineEvalService

router = APIRouter()
logger = logging.getLogger(__name__)
service = OnlineEvalService()


class QualityScoreRunRequest(BaseModel):
    sample_size: int = 50


@router.get("")
async def list_feedback(
    sentiment: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    agent_type: str | None = Query(None),
    category: str | None = Query(None),
    search: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    items, total = await service.list_feedback(
        db=session,
        sentiment=sentiment,
        date_from=date_from,
        date_to=date_to,
        agent_type=agent_type,
        category=category,
        search=search,
        offset=offset,
        limit=limit,
    )
    return {
        "items": [
            {
                "id": f.id,
                "user_id": f.user_id,
                "thread_id": f.thread_id,
                "message_index": f.message_index,
                "score": f.score,
                "comment": f.comment,
                "category": f.category,
                "agent_type": f.agent_type,
                "confidence_score": f.confidence_score,
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in items
        ],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.post("/export-requests", response_model=ApprovalResponse)
async def request_feedback_export(
    filters: FeedbackExportFilters,
    actor: AuthorizationContext = Depends(get_authorized_auth_context),
    session: AsyncSession = Depends(get_session),
    compliance: ComplianceService = Depends(ComplianceService),
) -> ApprovalResponse:
    """Request approval for one exact confidential feedback export."""
    approval = await compliance.request_feedback_export(
        session,
        actor=actor,
        parameters=filters.operation_parameters(),
        now=utc_now(),
    )
    await session.commit()
    return ApprovalResponse.model_validate(approval)


@router.get("/export", response_model=SensitiveExportResponse)
async def export_feedback(
    approval_id: str,
    sentiment: Literal["up", "neutral", "down"] | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    agent_type: str | None = Query(None),
    category: str | None = Query(None),
    search: str | None = Query(None, max_length=128),
    actor: AuthorizationContext = Depends(get_authorized_auth_context),
    session: AsyncSession = Depends(get_session),
    compliance: ComplianceService = Depends(ComplianceService),
) -> SensitiveExportResponse:
    """Execute or retry the approved exact feedback export."""
    filters = FeedbackExportFilters(
        sentiment=sentiment,
        date_from=date_from,
        date_to=date_to,
        agent_type=agent_type,
        category=category,
        search=search,
    )
    try:
        artifact = await compliance.execute_feedback_export(
            session,
            actor=actor,
            approval_id=approval_id,
            parameters=filters.operation_parameters(),
            now=utc_now(),
        )
        await session.commit()
        return SensitiveExportResponse(
            artifact_id=artifact.id,
            filename=artifact.filename,
            content=artifact.content,
            record_count=artifact.record_count,
            expires_at=artifact.expires_at,
        )
    except ApprovalNotFoundError as error:
        await session.rollback()
        SENSITIVE_EXPORTS_TOTAL.labels(result="denied").inc()
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ApprovalExpiredError as error:
        await session.commit()
        SENSITIVE_EXPORTS_TOTAL.labels(result="denied").inc()
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ApprovalDeniedError as error:
        await session.rollback()
        SENSITIVE_EXPORTS_TOTAL.labels(result="denied").inc()
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ExportGenerationError as error:
        try:
            await session.commit()
        except Exception:
            await session.rollback()
        logger.error(
            "Sensitive export generation failed",
            extra={"operation": "feedback_export", "tenant_id": actor.tenant_id},
        )
        raise HTTPException(status_code=500, detail="Sensitive export generation failed") from error


@router.get("/csat")
async def get_csat_trend(
    days: int = Query(30, ge=1, le=365),
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    trend = await service.get_csat_trend(db=session, days=days)
    return {"days": days, "trend": trend}


@router.get("/stats")
async def get_feedback_stats(
    days: int = Query(30, ge=1, le=365),
    agent_type: str | None = Query(None),
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    stats = await service.get_feedback_stats(db=session, days=days, agent_type=agent_type)
    return {"days": days, **stats}


@router.post("/quality-score/run")
async def run_quality_score(
    request: QualityScoreRunRequest,
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    scores = await service.compute_quality_scores(db=session, sample_size=request.sample_size)
    return {"success": True, "scored_count": len(scores)}
