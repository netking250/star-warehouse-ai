"""Normalized business-adapter error model."""

from enum import StrEnum


class AdapterErrorCode(StrEnum):
    """Stable error codes shared by every business-system adapter."""

    NOT_FOUND = "not_found"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    VALIDATION = "validation_error"
    CONFLICT = "conflict"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    UPSTREAM_ERROR = "upstream_error"
    CIRCUIT_OPEN = "circuit_open"


class AdapterError(RuntimeError):
    """A safe, normalized failure returned by an upstream business system."""

    def __init__(
        self,
        code: AdapterErrorCode,
        message: str,
        *,
        service: str,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.service = service
        self.retryable = retryable
