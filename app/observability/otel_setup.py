"""OpenTelemetry setup for FastAPI and Celery instrumentation."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import FastAPI
from opentelemetry import propagate, trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, SpanLimits, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from app.core.branding import APP_VERSION
from app.core.config import settings

_provider: TracerProvider | None = None
_celery_instrumented = False


class NoOpSpanExporter(SpanExporter):
    """No-op span exporter for environments without an OTLP collector."""

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        """Accept spans without performing I/O when no collector is configured."""
        _ = spans
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        """Shut down the no-op exporter."""
        return None

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Report a successful no-op flush."""
        _ = timeout_millis
        return True


def setup_otel_tracing(service_name: str | None = None) -> TracerProvider:
    """Configure bounded OpenTelemetry tracing with OTLP or no-op export."""
    global _provider
    if _provider is not None:
        return _provider

    resource = Resource.create(
        {
            "service.name": service_name or settings.OTEL_SERVICE_NAME or settings.SERVICE_NAME,
            "service.version": APP_VERSION,
            "deployment.environment": settings.ENVIRONMENT,
        }
    )
    provider = TracerProvider(
        resource=resource,
        span_limits=SpanLimits(
            max_attributes=64,
            max_events=128,
            max_links=32,
            max_attribute_length=256,
        ),
    )

    endpoint = settings.OTEL_EXPORTER_OTLP_ENDPOINT
    exporter = OTLPSpanExporter(endpoint=endpoint, timeout=5) if endpoint else NoOpSpanExporter()

    processor = BatchSpanProcessor(
        exporter,
        max_queue_size=2048,
        max_export_batch_size=512,
        schedule_delay_millis=5000,
        export_timeout_millis=5000,
    )
    provider.add_span_processor(processor)

    # TaskContext uses the standard carrier representation. Make the propagator explicit so an
    # environment-level propagator setting cannot silently change the trusted handoff format.
    propagate.set_global_textmap(TraceContextTextMapPropagator())
    trace.set_tracer_provider(provider)
    _provider = provider
    return provider


def instrument_fastapi(app: FastAPI) -> None:
    """Instrument a FastAPI application with OpenTelemetry."""
    app_state = getattr(app, "state", None)
    if app_state is not None and getattr(app_state, "otel_fastapi_instrumented", False):
        return
    FastAPIInstrumentor.instrument_app(app)
    if app_state is not None:
        app_state.otel_fastapi_instrumented = True


def setup_celery_tracing() -> None:
    """Instrument Celery with OpenTelemetry tracing.

    Must be called after the Celery app is created and before tasks are
    dispatched so that trace context is automatically propagated across
    the broker boundary.
    """
    global _celery_instrumented
    if _celery_instrumented:
        return
    CeleryInstrumentor().instrument()
    _celery_instrumented = True
