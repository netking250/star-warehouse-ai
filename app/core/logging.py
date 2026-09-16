import contextvars
import logging
import re
import uuid
from collections.abc import Generator, Mapping
from contextlib import contextmanager

correlation_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)

_SENSITIVE_QUERY_PATTERN = re.compile(
    r"([?&](?:token|access_token|refresh_token)=)[^&\s\"]+",
    re.IGNORECASE,
)
_BEARER_PATTERN = re.compile(r"(?i)(\bBearer\s+)[A-Za-z0-9._~+/=-]+")
_SENSITIVE_HEADER_PATTERN = re.compile(
    r"(?i)(\b(?:Cookie|Set-Cookie|X-CSRF-Token)\s*[:=]\s*)[^\r\n]+"
)
_SENSITIVE_LOG_KEYS = frozenset(
    {
        "authorization",
        "cookie",
        "set-cookie",
        "token",
        "jwt",
        "credential",
        "credentials",
        "x-csrf-token",
        "access-token",
        "refresh-token",
        "api-key",
        "password",
        "secret",
        "prompt",
        "messages",
        "completion",
        "rag-context",
        "request-body",
        "response-body",
        "context",
        "trace-context",
    }
)
_SENSITIVE_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)(?<![?&])(['\"]?(?:authorization|cookie|set-cookie|token|jwt|credential|credentials|"
    r"x-csrf-token|access[_-]?token|"
    r"refresh[_-]?token|api[_-]?key|password|secret|prompt|messages|completion|"
    r"rag[_-]?context|request[_-]?body|response[_-]?body)['\"]?\s*[:=]\s*)"
    r"(\"[^\"]*\"|'[^']*'|[^,}\r\n]*)"
)


def _normalized_key(key: object) -> str:
    """Normalize a structured log key for sensitive-field matching."""
    return str(key).strip().lower().replace("_", "-")


def _is_sensitive_key(key: object) -> bool:
    """Return whether a structured field may contain a credential or sensitive body."""
    normalized = _normalized_key(key)
    return (
        normalized in _SENSITIVE_LOG_KEYS
        or normalized.endswith(("-password", "-secret", "-api-key"))
        or normalized.endswith(("-access-token", "-refresh-token", "-csrf-token"))
    )


def redact_log_value(value: object, *, key: object | None = None) -> object:
    """Recursively redact credentials and sensitive request/response fields."""
    if _is_sensitive_key(key):
        return "[REDACTED]"
    if isinstance(value, str):
        redacted = _SENSITIVE_QUERY_PATTERN.sub(r"\1%5BREDACTED%5D", value)
        redacted = _BEARER_PATTERN.sub(r"\1[REDACTED]", redacted)
        redacted = _SENSITIVE_HEADER_PATTERN.sub(r"\1[REDACTED]", redacted)
        return _SENSITIVE_ASSIGNMENT_PATTERN.sub(r"\1[REDACTED]", redacted)
    if isinstance(value, Mapping):
        return {
            field: redact_log_value(field_value, key=field) for field, field_value in value.items()
        }
    if isinstance(value, tuple):
        return tuple(redact_log_value(item) for item in value)
    if isinstance(value, list):
        return [redact_log_value(item) for item in value]
    if isinstance(value, set):
        return {redact_log_value(item) for item in value}
    return value


class SensitiveQueryFilter(logging.Filter):
    """Redact authentication credentials from query strings and request headers."""

    @staticmethod
    def _redact(value: object) -> object:
        """Keep the historical helper name while using recursive redaction."""
        return redact_log_value(value)

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_log_value(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(redact_log_value(item) for item in record.args)
        elif isinstance(record.args, Mapping):
            record.args = {
                key: redact_log_value(item, key=key) for key, item in record.args.items()
            }
        for key, value in tuple(record.__dict__.items()):
            if key in {"msg", "args", "exc_info", "exc_text", "stack_info"}:
                continue
            setattr(record, key, redact_log_value(value, key=key))
        return True


class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            cid = correlation_id.get()
        except LookupError:
            cid = None
        record.correlation_id = cid if cid is not None else "-"
        return True


def set_correlation_id(cid: str) -> contextvars.Token[str | None]:
    """Bind a correlation ID and return a token that restores the prior value."""
    return correlation_id.set(cid)


def reset_correlation_id(token: contextvars.Token[str | None]) -> None:
    """Restore the correlation ID value that preceded a request/task scope."""
    correlation_id.reset(token)


@contextmanager
def correlation_scope(cid: str) -> Generator[str, None, None]:
    """Bind a correlation ID for a bounded request or socket scope."""
    token = set_correlation_id(cid)
    try:
        yield cid
    finally:
        reset_correlation_id(token)


def get_correlation_id() -> str:
    """Return the active request correlation ID."""
    return correlation_id.get() or "-"


def generate_correlation_id() -> str:
    """Generate a short, log-safe correlation identifier."""
    return uuid.uuid4().hex[:16]


_CORRELATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def normalize_correlation_id(value: str | None) -> str:
    """Accept only bounded diagnostic IDs and generate one for untrusted input."""
    candidate = value.strip() if value is not None else ""
    return candidate if _CORRELATION_ID_PATTERN.fullmatch(candidate) else generate_correlation_id()
