import contextvars
import logging
import re
import uuid

correlation_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)

_SENSITIVE_QUERY_PATTERN = re.compile(r"([?&](?:token|access_token)=)[^&\s\"]+", re.IGNORECASE)


class SensitiveQueryFilter(logging.Filter):
    """Redact authentication tokens embedded in request query strings."""

    @staticmethod
    def _redact(value: object) -> object:
        if isinstance(value, str):
            return _SENSITIVE_QUERY_PATTERN.sub(r"\1%5BREDACTED%5D", value)
        if isinstance(value, tuple):
            return tuple(SensitiveQueryFilter._redact(item) for item in value)
        if isinstance(value, dict):
            return {key: SensitiveQueryFilter._redact(item) for key, item in value.items()}
        return value

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self._redact(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(self._redact(item) for item in record.args)
        elif record.args is not None:
            record.args = {key: self._redact(item) for key, item in record.args.items()}
        return True


class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            cid = correlation_id.get()
        except LookupError:
            cid = None
        record.correlation_id = cid if cid is not None else "-"
        return True


def set_correlation_id(cid: str) -> None:
    correlation_id.set(cid)


def get_correlation_id() -> str:
    """Return the active request correlation ID."""
    return correlation_id.get() or "-"


def generate_correlation_id() -> str:
    return uuid.uuid4().hex[:16]
