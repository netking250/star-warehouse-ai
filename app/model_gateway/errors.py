"""Stable error taxonomy for model providers and gateway validation."""

from __future__ import annotations

from enum import StrEnum


class ModelErrorCategory(StrEnum):
    """Safe provider failure categories consumed by later policy layers."""

    AUTHENTICATION = "authentication"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    BAD_REQUEST = "bad_request"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    INVALID_RESPONSE = "invalid_response"
    UNKNOWN = "unknown"


class ModelGatewayError(Exception):
    """Normalized failure without raw provider response bodies or credentials."""

    def __init__(
        self,
        category: ModelErrorCategory,
        message: str,
        *,
        provider: str | None = None,
        model: str | None = None,
        provider_request_id: str | None = None,
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.provider = provider
        self.model = model
        self.provider_request_id = provider_request_id
        self.retry_after_seconds = retry_after_seconds


class ModelConfigurationError(ValueError):
    """Reject invalid routes or provider registry configuration before use."""
