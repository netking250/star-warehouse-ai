"""Focused regression coverage for API OpenTelemetry bootstrap ordering."""

from __future__ import annotations

import json
import logging

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind

import tests._db_config  # noqa: F401  must run before importing application settings
from app.core.logging import CorrelationIdFilter
from app.core.structured_logging import JsonFormatter
from app.main import (
    app as api_app,
)
from app.main import (
    correlation_id_middleware,
    trace_id_middleware,
)
from app.observability.otel_setup import instrument_fastapi


class _JsonCaptureHandler(logging.Handler):
    """Capture formatted JSON records emitted while a request span is active."""

    def __init__(self) -> None:
        super().__init__()
        self.payloads: list[dict[str, object]] = []
        self.addFilter(CorrelationIdFilter())
        self.setFormatter(JsonFormatter())

    def emit(self, record: logging.LogRecord) -> None:
        self.payloads.append(json.loads(self.format(record)))


@pytest.mark.asyncio
async def test_api_tracing_is_active_before_first_request_and_correlates_logs() -> None:
    """The API bootstrap must create a recording server span before ASGI stack caching."""
    assert getattr(api_app.state, "otel_fastapi_instrumented", False) is True
    assert getattr(api_app, "_is_instrumented_by_opentelemetry", False) is True

    provider = trace.get_tracer_provider()
    assert isinstance(provider, TracerProvider)
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    probe = FastAPI()
    probe.middleware("http")(correlation_id_middleware)
    probe.middleware("http")(trace_id_middleware)
    capture = _JsonCaptureHandler()
    probe_logger = logging.getLogger("tests.observability.api_trace_probe")
    probe_logger.addHandler(capture)
    probe_logger.setLevel(logging.INFO)
    probe_logger.propagate = False

    @probe.get("/probe")
    async def _probe() -> dict[str, str]:
        probe_logger.info("API trace probe", extra={"event": "api_trace_probe"})
        return {"status": "ok"}

    instrument_fastapi(probe)
    trace_id = "17000000000000000000000000000017"
    correlation_id = "t17-api-trace-regression"
    try:
        async with AsyncClient(
            transport=ASGITransport(app=probe), base_url="http://test"
        ) as client:
            response = await client.get(
                "/probe",
                headers={
                    "traceparent": f"00-{trace_id}-0000000000000017-01",
                    "X-Correlation-ID": correlation_id,
                },
            )
        provider.force_flush()
    finally:
        probe_logger.removeHandler(capture)
        FastAPIInstrumentor.uninstrument_app(probe)

    server_spans = [span for span in exporter.get_finished_spans() if span.kind is SpanKind.SERVER]
    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == correlation_id
    assert response.headers["X-Trace-ID"] == trace_id
    assert len(server_spans) == 1
    assert format(server_spans[0].context.trace_id, "032x") == trace_id
    assert capture.payloads[0]["correlation_id"] == correlation_id
    assert capture.payloads[0]["trace_id"] == trace_id
    assert capture.payloads[0]["span_id"] == format(server_spans[0].context.span_id, "016x")
