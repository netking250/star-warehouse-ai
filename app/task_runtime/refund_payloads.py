"""Typed sanitized payloads for refund background tasks."""

from pydantic import BaseModel, ConfigDict, Field


class RefundPaymentPayload(BaseModel):
    """Minimal data required to execute an approved refund payment."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    refund_id: int = Field(gt=0)
    amount: float = Field(gt=0)
    payment_method: str = Field(min_length=1, max_length=64)


class RefundSmsPayload(BaseModel):
    """PII-free reference used to resolve an SMS recipient in the worker."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    refund_id: int = Field(gt=0)


class AuditNotificationPayload(BaseModel):
    """Identifier required to create an administrator audit notification."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    audit_log_id: int = Field(gt=0)
