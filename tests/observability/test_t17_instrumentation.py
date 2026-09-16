"""Focused T17 instrumentation, safety, and correlation regressions."""

from __future__ import annotations

import json
import logging
from types import SimpleNamespace
from typing import Protocol, cast
from unittest.mock import patch

import pytest

import tests._db_config  # noqa: F401  must run before importing application settings
from app.core.logging import CorrelationIdFilter, correlation_scope
from app.core.structured_logging import JsonFormatter
from app.model_gateway.contracts import ModelCandidate, ModelCapability, ModelMessage, ModelRequest
from app.model_gateway.failure_policy import ModelFailurePolicy, ModelFailurePolicyConfig
from app.observability.celery import (
    on_task_failure,
    on_task_postrun,
    on_task_prerun,
    on_task_received,
)
from app.observability.database import _statement_operation
from app.observability.metrics import (
    ASYNC_JOB_DURATION_SECONDS,
    ASYNC_JOBS_TOTAL,
    CELERY_TASK_DURATION_SECONDS,
    CELERY_TASK_EVENTS_TOTAL,
    CONVERSATION_RUN_DURATION_SECONDS,
    CONVERSATION_TERMINALS_TOTAL,
    DB_CONNECTION_ERRORS_TOTAL,
    DB_CONNECTIONS_IN_USE,
    DB_QUERY_DURATION_SECONDS,
    DEPENDENCY_HEALTH,
    HTTP_ERRORS_TOTAL,
    HTTP_REQUESTS_TOTAL,
    MODEL_CIRCUIT_STATE,
    MODEL_LOGICAL_REQUEST_DURATION_SECONDS,
    MODEL_LOGICAL_REQUESTS_TOTAL,
    MODEL_PROVIDER_ATTEMPTS_TOTAL,
    OUTBOX_DELIVERY_ATTEMPTS_TOTAL,
    OUTBOX_PUBLISH_FAILURE_TOTAL,
    OUTBOX_PUBLISH_TOTAL,
    normalize_route_label,
    record_conversation_duration,
    record_conversation_terminal,
    record_database_connection_error,
    record_database_query_duration,
    record_http_request,
    record_model_fallback,
    record_outbox_delivery_attempt,
    record_outbox_publish,
    set_model_circuit_state,
)
from app.task_runtime.context import build_task_context
from app.task_runtime.envelope import TaskEnvelope


class _Route:
    path = "/api/v1/orders/{order_id}"


class _MetricValue(Protocol):
    def get(self) -> float: ...


class _MetricSample(Protocol):
    name: str
    value: float


class _HistogramChild(Protocol):
    def _samples(self) -> tuple[_MetricSample, ...]: ...


class _Metric(Protocol):
    _value: _MetricValue

    def labels(self, **labels: str) -> _Metric: ...


class _FakeModelGateway:
    """Minimal provider-neutral gateway for policy instrumentation tests."""

    def __init__(self, candidate: ModelCandidate) -> None:
        self.candidate = candidate

    def resolve(self, route: str, required_capabilities: frozenset[ModelCapability]):
        del route, required_capabilities
        return (self.candidate,)

    async def invoke(self, candidate: ModelCandidate, request: ModelRequest):
        from app.model_gateway.contracts import ModelResponse

        return ModelResponse(
            content="ok",
            finish_reason="stop",
            provider=candidate.provider,
            model=candidate.model,
        )

    def stream(self, candidate: ModelCandidate, request: ModelRequest):
        del candidate, request
        raise AssertionError("stream is not used by this test")


def _metric_value(metric: object, **labels: str) -> float:
    typed_metric = cast(_Metric, metric)
    labelled = typed_metric.labels(**labels) if labels else typed_metric
    return float(labelled._value.get())


def _histogram_count(metric: object, **labels: str) -> float:
    """Read a histogram observation count through its public test shape."""
    typed_metric = cast(_Metric, metric)
    labelled = cast(_HistogramChild, typed_metric.labels(**labels))
    count_sample = next(sample for sample in labelled._samples() if sample.name == "_count")
    return count_sample.value


def test_http_route_metrics_use_template_and_status_class() -> None:
    """HTTP metrics must never fall back to a concrete resource URL."""
    before = _metric_value(
        HTTP_REQUESTS_TOTAL,
        route="/api/v1/orders/{order_id}",
        method="GET",
        status_class="2xx",
    )

    record_http_request(
        route=_Route(),
        method="GET",
        status_code=200,
        duration_seconds=0.01,
    )

    assert (
        _metric_value(
            HTTP_REQUESTS_TOTAL,
            route="/api/v1/orders/{order_id}",
            method="GET",
            status_class="2xx",
        )
        == before + 1
    )
    assert normalize_route_label("/api/v1/orders/123456") == "unmatched"


def test_database_metrics_use_only_bounded_engine_and_operation_labels() -> None:
    """Database telemetry records aggregate shape, never SQL text or bind values."""
    assert _statement_operation("SELECT secret FROM users WHERE token = 'private'") == "SELECT"
    assert _statement_operation("WITH private_data AS (SELECT 1) SELECT 1") == "OTHER"
    query_before = _histogram_count(
        DB_QUERY_DURATION_SECONDS,
        engine="async",
        operation="SELECT",
    )
    connections_before = DB_CONNECTIONS_IN_USE.labels(engine="sync")._value.get()
    errors_before = DB_CONNECTION_ERRORS_TOTAL.labels(
        engine="async", category="connection"
    )._value.get()

    record_database_query_duration(
        engine="async",
        operation="SELECT",
        duration_seconds=0.01,
    )
    record_database_connection_error(engine="async", category="socket credentials private")

    assert (
        _histogram_count(
            DB_QUERY_DURATION_SECONDS,
            engine="async",
            operation="SELECT",
        )
        == query_before + 1
    )
    assert DB_CONNECTIONS_IN_USE.labels(engine="sync")._value.get() == connections_before
    assert DB_CONNECTION_ERRORS_TOTAL.labels(engine="async", category="unknown")._value.get() >= 1
    assert (
        DB_CONNECTION_ERRORS_TOTAL.labels(engine="async", category="connection")._value.get()
        == errors_before
    )


def test_new_metric_families_have_no_identity_or_payload_labels() -> None:
    """New operational metric families must remain low-cardinality by construction."""
    forbidden = {
        "tenant_id",
        "user_id",
        "request_id",
        "correlation_id",
        "conversation_id",
        "run_id",
        "email",
        "prompt",
        "messages",
        "exception",
        "url",
    }
    collectors = (
        HTTP_REQUESTS_TOTAL,
        HTTP_ERRORS_TOTAL,
        CELERY_TASK_EVENTS_TOTAL,
        CELERY_TASK_DURATION_SECONDS,
        ASYNC_JOBS_TOTAL,
        ASYNC_JOB_DURATION_SECONDS,
        MODEL_LOGICAL_REQUESTS_TOTAL,
        MODEL_PROVIDER_ATTEMPTS_TOTAL,
        MODEL_CIRCUIT_STATE,
        CONVERSATION_RUN_DURATION_SECONDS,
        CONVERSATION_TERMINALS_TOTAL,
        DB_QUERY_DURATION_SECONDS,
        DB_CONNECTIONS_IN_USE,
        DB_CONNECTION_ERRORS_TOTAL,
        DEPENDENCY_HEALTH,
    )

    assert all(not forbidden.intersection(collector._labelnames) for collector in collectors)


def test_structured_error_log_redacts_credentials_and_sensitive_bodies() -> None:
    """JSON formatting must be safe even when a handler filter was not separately installed."""
    record = logging.LogRecord(
        name="test.observability",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="provider failure api_key=secret-key token=raw-token prompt=private question",
        args=(),
        exc_info=None,
    )
    record.authorization = "Bearer raw-jwt"
    record.request_body = {"prompt": "private question", "password": "raw-password"}
    record.trace_context = {"traceparent": "raw-carrier"}

    output = JsonFormatter().format(record)

    assert "secret-key" not in output
    assert "private question" not in output
    assert "raw-jwt" not in output
    assert "raw-token" not in output
    assert "private question" not in output
    assert "raw-password" not in output
    assert "raw-carrier" not in output
    assert json.loads(output)["level"] == "ERROR"


def test_log_contains_correlation_and_trace_ids_without_using_them_as_metric_labels() -> None:
    """A safe correlation scope joins a log record to a trace for operator drill-down."""
    span_context = SimpleNamespace(is_valid=True, trace_id=0xABC, span_id=0xDEF)
    span = SimpleNamespace(get_span_context=lambda: span_context)
    record = logging.LogRecord(
        name="test.observability",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="synthetic operation",
        args=(),
        exc_info=None,
    )
    with (
        patch("app.core.structured_logging.trace.get_current_span", return_value=span),
        correlation_scope("t17-correlation"),
    ):
        CorrelationIdFilter().filter(record)
        output = json.loads(JsonFormatter().format(record))

    assert output["correlation_id"] == "t17-correlation"
    assert output["trace_id"] == "00000000000000000000000000000abc"
    assert output["span_id"] == f"{0xDEF:016x}"


def test_task_envelope_preserves_safe_trace_carrier_across_json_handoff() -> None:
    """Only the accepted W3C carrier representation crosses the async boundary."""
    context = build_task_context(
        task_name="memory.sync_vector",
        tenant_id="tenant-t17",
        user_id=7,
        correlation_id="t17-correlation",
        trace_id="1" * 32,
        trace_context={"traceparent": f"00-{'1' * 32}-{'2' * 16}-01"},
    )
    envelope = TaskEnvelope(task_context=context, payload={"memory_id": 9})
    restored = TaskEnvelope.from_message(json.loads(json.dumps(envelope.to_message())))

    assert restored.task_context.trace_context == {"traceparent": f"00-{'1' * 32}-{'2' * 16}-01"}
    assert restored.payload == {"memory_id": 9}


def test_celery_success_and_failure_lifecycle_metrics_are_bounded() -> None:
    """Worker lifecycle signals record outcomes without task arguments or IDs as labels."""
    sender = SimpleNamespace(
        name="memory.sync_vector",
        request=SimpleNamespace(id="task-1", delivery_info={"routing_key": "critical"}),
    )
    started_before = _metric_value(
        CELERY_TASK_EVENTS_TOTAL,
        task_type="memory.sync_vector",
        queue="critical",
        outcome="started",
    )
    pending_before = _metric_value(
        ASYNC_JOBS_TOTAL,
        job_type="memory.sync_vector",
        status="pending",
    )
    running_before = _metric_value(
        ASYNC_JOBS_TOTAL,
        job_type="memory.sync_vector",
        status="running",
    )
    completed_before = _metric_value(
        ASYNC_JOBS_TOTAL,
        job_type="memory.sync_vector",
        status="completed",
    )

    on_task_received(sender=sender, request=sender.request)
    on_task_prerun(sender=sender, task_id="task-1", task=sender)
    on_task_postrun(sender=sender, task_id="task-1", state="SUCCESS", task=sender)

    assert (
        _metric_value(
            ASYNC_JOBS_TOTAL,
            job_type="memory.sync_vector",
            status="pending",
        )
        == pending_before + 1
    )
    assert (
        _metric_value(
            ASYNC_JOBS_TOTAL,
            job_type="memory.sync_vector",
            status="running",
        )
        == running_before + 1
    )

    assert (
        _metric_value(
            CELERY_TASK_EVENTS_TOTAL,
            task_type="memory.sync_vector",
            queue="critical",
            outcome="started",
        )
        == started_before + 1
    )
    assert (
        _metric_value(
            ASYNC_JOBS_TOTAL,
            job_type="memory.sync_vector",
            status="completed",
        )
        == completed_before + 1
    )

    on_task_prerun(sender=sender, task_id="task-2", task=sender)
    on_task_failure(sender=sender, task_id="task-2", task=sender, request=sender.request)
    on_task_postrun(sender=sender, task_id="task-2", state="FAILURE", task=sender)
    assert (
        _metric_value(
            CELERY_TASK_EVENTS_TOTAL,
            task_type="memory.sync_vector",
            queue="critical",
            outcome="failed",
        )
        >= 1
    )


def test_outbox_publish_and_failure_metrics_are_separate_from_attempts() -> None:
    """Outbox delivery attempts and publication outcomes remain independently queryable."""
    attempts_before = _metric_value(OUTBOX_DELIVERY_ATTEMPTS_TOTAL)
    published_before = _metric_value(OUTBOX_PUBLISH_TOTAL)
    failures_before = _metric_value(OUTBOX_PUBLISH_FAILURE_TOTAL)

    record_outbox_delivery_attempt()
    record_outbox_publish(success=True)
    record_outbox_delivery_attempt()
    record_outbox_publish(success=False)

    assert _metric_value(OUTBOX_DELIVERY_ATTEMPTS_TOTAL) == attempts_before + 2
    assert _metric_value(OUTBOX_PUBLISH_TOTAL) == published_before + 1
    assert _metric_value(OUTBOX_PUBLISH_FAILURE_TOTAL) == failures_before + 1


@pytest.mark.asyncio
async def test_model_logical_request_is_one_event_for_one_provider_attempt() -> None:
    """A successful policy call yields one logical event and one terminal attempt event."""
    candidate = ModelCandidate(
        provider="synthetic",
        model="synthetic-model",
        capabilities=frozenset({ModelCapability.CHAT}),
        timeout_seconds=1.0,
    )
    gateway = _FakeModelGateway(candidate)
    policy = ModelFailurePolicy(
        ModelFailurePolicyConfig(
            max_attempts_per_candidate=1,
            max_total_attempts=1,
            base_backoff_seconds=0,
            max_backoff_seconds=0,
            circuit_failure_threshold=5,
        )
    )
    request = ModelRequest(
        route="t17_route",
        messages=(ModelMessage(role="user", content="synthetic"),),
    )
    logical_before = _metric_value(
        MODEL_LOGICAL_REQUESTS_TOTAL,
        route="t17_route",
        outcome="success",
        category="none",
    )
    attempts_before = _metric_value(
        MODEL_PROVIDER_ATTEMPTS_TOTAL,
        provider="synthetic",
        route="t17_route",
        outcome="success",
        category="none",
    )

    result = await policy.invoke(gateway, request, candidates=(candidate,))

    assert result.content == "ok"
    assert (
        _metric_value(
            MODEL_LOGICAL_REQUESTS_TOTAL,
            route="t17_route",
            outcome="success",
            category="none",
        )
        == logical_before + 1
    )
    assert (
        _metric_value(
            MODEL_PROVIDER_ATTEMPTS_TOTAL,
            provider="synthetic",
            route="t17_route",
            outcome="success",
            category="none",
        )
        == attempts_before + 1
    )
    duration = MODEL_LOGICAL_REQUEST_DURATION_SECONDS.labels(route="t17_route", outcome="success")
    count_sample = next(
        sample for sample in cast(_HistogramChild, duration)._samples() if sample.name == "_count"
    )
    assert count_sample.value >= 1


def test_model_fallback_and_circuit_state_metrics_are_read_only_signals() -> None:
    """Fallback and breaker state helpers expose bounded operational facts only."""
    record_model_fallback(provider="synthetic", outcome="candidate_exhausted")
    set_model_circuit_state(provider="synthetic", state="OPEN")

    assert MODEL_CIRCUIT_STATE.labels(provider="synthetic", state="open")._value.get() == 1
    assert MODEL_CIRCUIT_STATE.labels(provider="synthetic", state="closed")._value.get() == 0


def test_conversation_terminal_metrics_have_no_run_identity_labels() -> None:
    """Runtime metrics describe terminal behavior, not individual conversations."""
    before = _metric_value(
        CONVERSATION_TERMINALS_TOTAL,
        status="failed",
        category="executor_error",
    )
    record_conversation_terminal(status="failed", category="EXECUTOR_ERROR")
    record_conversation_duration(terminal_status="FAILED", duration_seconds=0.25)

    assert (
        _metric_value(
            CONVERSATION_TERMINALS_TOTAL,
            status="failed",
            category="executor_error",
        )
        == before + 1
    )


@pytest.mark.asyncio
async def test_metric_recording_failure_does_not_break_model_business_action() -> None:
    """A broken metrics sink cannot turn a successful provider response into a failure."""
    candidate = ModelCandidate(
        provider="synthetic-failure-sink",
        model="synthetic-model",
        capabilities=frozenset({ModelCapability.CHAT}),
        timeout_seconds=1.0,
    )
    policy = ModelFailurePolicy(
        ModelFailurePolicyConfig(
            max_attempts_per_candidate=1,
            max_total_attempts=1,
            base_backoff_seconds=0,
            max_backoff_seconds=0,
        )
    )
    request = ModelRequest(
        route="t17_failure_sink",
        messages=(ModelMessage(role="user", content="synthetic"),),
    )

    with patch(
        "app.model_gateway.failure_policy.record_model_logical_request",
        side_effect=RuntimeError("metrics unavailable"),
    ):
        result = await policy.invoke(_FakeModelGateway(candidate), request)

    assert result.content == "ok"
