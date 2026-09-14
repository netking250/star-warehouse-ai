"""Transport schemas for compliance lifecycle controls."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.compliance import ApprovalStatus


class FeedbackExportFilters(BaseModel):
    """Material filters bound into a feedback export approval."""

    sentiment: Literal["up", "neutral", "down"] | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    agent_type: str | None = Field(default=None, max_length=32)
    category: str | None = Field(default=None, max_length=32)
    search: str | None = Field(default=None, max_length=128)

    def operation_parameters(self) -> dict[str, object]:
        """Return deterministic JSON-compatible material parameters."""
        return {
            key: value.isoformat() if isinstance(value, datetime) else value
            for key, value in self.model_dump().items()
            if value is not None
        }


class ApprovalDecisionRequest(BaseModel):
    """Approve or reject one exact sensitive operation."""

    decision: Literal["APPROVE", "REJECT"]


class ApprovalResponse(BaseModel):
    """Approval state without raw export content."""

    id: str
    operation_type: str
    requester_user_id: int
    status: ApprovalStatus
    operation_payload_hash: str
    operation_parameters: dict[str, object]
    requested_at: datetime
    expires_at: datetime
    approver_user_id: int | None
    decision_at: datetime | None
    executed_at: datetime | None

    model_config = {"from_attributes": True}


class SensitiveExportResponse(BaseModel):
    """Authorized short-lived export artifact returned to its requester."""

    artifact_id: str
    filename: str
    content: str
    record_count: int
    expires_at: datetime


class RetentionRunRequest(BaseModel):
    """Optional bounded batch override for an inspected retention run."""

    batch_limit: int | None = Field(default=None, ge=1, le=1000)


class RetentionRunResponse(BaseModel):
    """Inspectable bounded retention result."""

    dataset: str
    tenant_id: str
    dry_run: bool
    eligible_count: int
    processed_count: int
    failed_count: int
    record_ids: tuple[str, ...]
