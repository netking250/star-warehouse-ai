"""Sensitive-operation policy and canonical parameter binding."""

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime

from app.authorization.policy import Scope
from app.compliance.classification import DataClassification


@dataclass(frozen=True, slots=True)
class SensitiveOperationPolicy:
    """Approval requirements for one real sensitive operation."""

    operation_type: str
    classification: DataClassification
    request_scope: Scope
    approval_scope: Scope
    approval_required: bool
    separation_of_duties: bool
    ttl_seconds: int


FEEDBACK_EXPORT = SensitiveOperationPolicy(
    operation_type="feedback.export",
    classification=DataClassification.CONFIDENTIAL,
    request_scope=Scope.EXPORTS_REQUEST,
    approval_scope=Scope.EXPORTS_APPROVE,
    approval_required=True,
    separation_of_duties=True,
    ttl_seconds=900,
)

SENSITIVE_OPERATION_POLICIES = {FEEDBACK_EXPORT.operation_type: FEEDBACK_EXPORT}


def canonical_operation_parameters(parameters: dict[str, object]) -> dict[str, object]:
    """Normalize a small filter snapshot without retaining export contents."""
    normalized: dict[str, object] = {}
    for key in sorted(parameters):
        value = parameters[key]
        if value is None:
            continue
        if isinstance(value, (datetime, date)):
            normalized[key] = value.isoformat()
        elif isinstance(value, (str, int, float, bool)):
            normalized[key] = value
        else:
            raise ValueError("Operation parameters must contain only scalar values")
    return normalized


def operation_hash(
    *, tenant_id: str, operation_type: str, requester_user_id: int, parameters: dict[str, object]
) -> str:
    """Bind approval to tenant, operation, requester, and exact material parameters."""
    payload = {
        "tenant_id": tenant_id,
        "operation_type": operation_type,
        "requester_user_id": requester_user_id,
        "parameters": canonical_operation_parameters(parameters),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
