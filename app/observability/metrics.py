"""Prometheus metrics for Star Warehouse AI.

Provides custom application metrics alongside the existing OpenTelemetry tracing.
All metric recording functions are async-safe and non-blocking.
"""

from __future__ import annotations

import re
from typing import cast

from prometheus_client import (  # type: ignore[import-not-found] - prometheus-client is installed but lacks stubs
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)


def _get_or_create_gauge(name: str, description: str, labels: list[str] | None = None) -> Gauge:
    """Return an existing Gauge or create a new one."""
    try:
        return Gauge(name, description, labels or [])
    except ValueError:
        return cast(Gauge, REGISTRY._names_to_collectors[name])


def _get_or_create_counter(name: str, description: str, labels: list[str] | None = None) -> Counter:
    """Return an existing Counter or create a new one."""
    try:
        return Counter(name, description, labels or [])
    except ValueError:
        return cast(Counter, REGISTRY._names_to_collectors[name])


def _get_or_create_histogram(
    name: str,
    description: str,
    labels: list[str] | None = None,
    buckets: tuple[float, ...] | None = None,
) -> Histogram:
    """Return an existing Histogram or create a new one."""
    try:
        if buckets is None:
            return Histogram(name, description, labels or [])
        return Histogram(name, description, labels or [], buckets=buckets)
    except ValueError:
        return cast(Histogram, REGISTRY._names_to_collectors[name])


CHAT_REQUESTS_TOTAL = _get_or_create_counter(
    "chat_requests_total",
    "Total number of chat requests received.",
    ["intent_category", "final_agent"],
)

CHAT_ERRORS_TOTAL = _get_or_create_counter(
    "chat_errors_total",
    "Total number of chat request errors.",
    ["error_type"],
)

MODEL_ATTEMPTS_TOTAL = _get_or_create_counter(
    "model_attempts_total",
    "Model provider attempts by provider and outcome.",
    ["provider", "outcome"],
)

MODEL_RETRIES_TOTAL = _get_or_create_counter(
    "model_retries_total",
    "Bounded model retries by provider and normalized failure category.",
    ["provider", "category"],
)

MODEL_FALLBACKS_TOTAL = _get_or_create_counter(
    "model_fallbacks_total",
    "Ordered model fallback transitions by source provider and outcome.",
    ["provider", "outcome"],
)

MODEL_CIRCUIT_TRANSITIONS_TOTAL = _get_or_create_counter(
    "model_circuit_transitions_total",
    "Model provider circuit state transitions.",
    ["provider", "from_state", "to_state"],
)

MODEL_DEGRADED_TOTAL = _get_or_create_counter(
    "model_degraded_total",
    "Safe static model degradation outcomes by route.",
    ["route"],
)

CHAT_LATENCY_SECONDS = _get_or_create_histogram(
    "chat_latency_seconds",
    "End-to-end chat request latency in seconds.",
    ["final_agent"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)

NODE_LATENCY_SECONDS = _get_or_create_histogram(
    "node_latency_seconds",
    "Individual graph node execution latency in seconds.",
    ["node_name"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

TOKEN_USAGE_TOTAL = _get_or_create_counter(
    "token_usage_total",
    "Total number of tokens consumed by LLM calls.",
    ["agent"],
)

CONTEXT_UTILIZATION_RATIO = _get_or_create_gauge(
    "context_utilization_ratio",
    "Ratio of context tokens used vs budget (0.0-1.0).",
)

HUMAN_TRANSFERS_TOTAL = _get_or_create_counter(
    "human_transfers_total",
    "Total number of requests transferred to human agents.",
    ["reason"],
)

INTENT_ACCURACY = _get_or_create_gauge(
    "intent_accuracy",
    "Accuracy of intent classification (0.0-1.0).",
    ["intent_category"],
)

RAG_PRECISION = _get_or_create_gauge(
    "rag_precision",
    "Precision of RAG retrieval (0.0-1.0).",
)

HALLUCINATION_RATE = _get_or_create_gauge(
    "hallucination_rate",
    "Rate of hallucinated responses (0.0-1.0).",
)

CONFIDENCE_SCORE = _get_or_create_histogram(
    "confidence_score",
    "Distribution of confidence scores.",
    buckets=(0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)

AGENT_CONTEXT_TOKENS = _get_or_create_gauge(
    "agent_context_tokens",
    "Context tokens per agent after state filtering.",
    ["agent_name"],
)

AGENT_CONTEXT_REDUCTION_RATIO = _get_or_create_gauge(
    "agent_context_reduction_ratio",
    "Ratio of tokens saved by context isolation (0.0-1.0).",
    ["agent_name"],
)

REDIS_CONNECTIONS_ACTIVE = _get_or_create_gauge(
    "redis_connections_active",
    "Number of active Redis connections in the pool.",
)

REDIS_CONNECTION_ERRORS_TOTAL = _get_or_create_counter(
    "redis_connection_errors_total",
    "Total number of Redis connection errors.",
    ["error_type"],
)

REDIS_OPERATION_LATENCY_SECONDS = _get_or_create_histogram(
    "redis_operation_latency_seconds",
    "Latency of Redis operations in seconds.",
    ["operation"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

REDIS_CACHE_HIT_RATIO = _get_or_create_gauge(
    "redis_cache_hit_ratio",
    "Cache hit ratio for Redis-backed caches (0.0-1.0).",
    ["cache_name"],
)

CHECKPOINT_SIZE_BYTES = _get_or_create_histogram(
    "checkpoint_size_bytes",
    "Compressed checkpoint size in bytes.",
    ["storage_type"],
    buckets=(128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536, 131072, 262144, 524288),
)

CHECKPOINT_COMPRESSION_RATIO = _get_or_create_histogram(
    "checkpoint_compression_ratio",
    "Compression ratio (uncompressed / compressed).",
    buckets=(1.0, 1.5, 2.0, 3.0, 5.0, 10.0, 20.0),
)

CHECKPOINT_CLEANUP_TOTAL = _get_or_create_counter(
    "checkpoint_cleanup_total",
    "Total number of old checkpoints removed by cleanup tasks.",
)

ANSWER_CORRECTNESS = _get_or_create_gauge(
    "answer_correctness",
    "Answer correctness score from evaluator (0.0-1.0).",
    ["agent_type"],
)

AGENT_LATENCY_SECONDS = _get_or_create_histogram(
    "agent_latency_seconds",
    "Agent execution latency in seconds.",
    ["agent_type"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

TOKEN_EFFICIENCY = _get_or_create_gauge(
    "token_efficiency",
    "Ratio of useful tokens to total tokens (0.0-1.0).",
    ["agent"],
)

TOKENS_TOTAL = _get_or_create_counter(
    "tokens_total",
    "Total tokens consumed across all agents.",
)

CACHE_HITS_TOTAL = _get_or_create_counter(
    "cache_hits_total",
    "Total cache hits.",
    ["cache_name"],
)

CACHE_MISSES_TOTAL = _get_or_create_counter(
    "cache_misses_total",
    "Total cache misses.",
    ["cache_name"],
)

HIGH_COST_REQUESTS_TOTAL = _get_or_create_counter(
    "high_cost_requests_total",
    "Total requests exceeding cost threshold.",
    ["agent"],
)

SAFETY_BLOCKS_TOTAL = _get_or_create_counter(
    "safety_blocks_total",
    "Total content moderation blocks.",
    ["layer", "reason"],
)

PII_DETECTIONS_TOTAL = _get_or_create_counter(
    "pii_detections_total",
    "Total PII detections by type.",
    ["pii_type", "source"],
)

INJECTION_ATTEMPTS_TOTAL = _get_or_create_counter(
    "injection_attempts_total",
    "Total prompt injection attempts detected.",
)

PII_BREACHES_TOTAL = _get_or_create_counter(
    "pii_breaches_total",
    "Total PII breaches (detections that bypassed filters).",
    ["pii_type"],
)

INJECTION_BYPASSED_TOTAL = _get_or_create_counter(
    "injection_bypassed_total",
    "Total prompt injection attempts that bypassed detection.",
)

RETENTION_RUNS_TOTAL = _get_or_create_counter(
    "retention_runs_total",
    "Total bounded retention runs by outcome.",
    ["result"],
)

RETENTION_RECORDS_PROCESSED_TOTAL = _get_or_create_counter(
    "retention_records_processed_total",
    "Total records processed by bounded retention policy.",
    ["dataset", "result"],
)

RETENTION_RUN_DURATION_SECONDS = _get_or_create_histogram(
    "retention_run_duration_seconds",
    "Duration of bounded retention runs in seconds.",
)

APPROVAL_REQUESTS_TOTAL = _get_or_create_counter(
    "approval_requests_total",
    "Total sensitive operation approval transitions.",
    ["operation", "result"],
)

APPROVAL_PENDING = _get_or_create_gauge(
    "approval_pending",
    "Current process-observed pending approval count.",
)

SENSITIVE_EXPORTS_TOTAL = _get_or_create_counter(
    "sensitive_exports_total",
    "Total sensitive export execution outcomes.",
    ["result"],
)

AUDIT_WRITE_FAILURES_TOTAL = _get_or_create_counter(
    "audit_write_failures_total",
    "Total compliance audit write failures.",
)

SAFETY_CHECKS_TOTAL = _get_or_create_counter(
    "safety_checks_total",
    "Total content safety checks performed.",
    ["layer"],
)

RATE_LIMIT_HITS_TOTAL = _get_or_create_counter(
    "rate_limit_hits_total",
    "Total rate limit hits by user.",
    ["limit_type"],
)

WEB_VITALS_LCP = _get_or_create_histogram(
    "web_vitals_lcp_seconds",
    "Largest Contentful Paint in seconds.",
    ["rating"],
    buckets=(0.1, 0.25, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0),
)

WEB_VITALS_CLS = _get_or_create_histogram(
    "web_vitals_cls_score",
    "Cumulative Layout Shift score.",
    ["rating"],
    buckets=(0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.5, 1.0),
)

WEB_VITALS_FID = _get_or_create_histogram(
    "web_vitals_fid_seconds",
    "First Input Delay in seconds.",
    ["rating"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

WEB_VITALS_FCP = _get_or_create_histogram(
    "web_vitals_fcp_seconds",
    "First Contentful Paint in seconds.",
    ["rating"],
    buckets=(0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0),
)

WEB_VITALS_TTFB = _get_or_create_histogram(
    "web_vitals_ttfb_seconds",
    "Time to First Byte in seconds.",
    ["rating"],
    buckets=(0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0),
)

OUTBOX_PUBLISH_TOTAL = _get_or_create_counter(
    "outbox_publish_total",
    "Total outbox events published to the configured task transport.",
)

OUTBOX_PUBLISH_FAILURE_TOTAL = _get_or_create_counter(
    "outbox_publish_failure_total",
    "Total outbox publication or publication-state failures.",
)

TASK_CONSUMER_TOTAL = _get_or_create_counter(
    "task_consumer_total",
    "Total protected task consumer outcomes.",
    ["task_type", "outcome"],
)

# T17 canonical operational metrics. Labels are intentionally limited to route templates and
# configured lifecycle categories. Identity values belong in safe log/span fields, never here.
HTTP_REQUESTS_TOTAL = _get_or_create_counter(
    "http_requests_total",
    "Total HTTP requests for application routes excluding telemetry and static asset probes.",
    ["route", "method", "status_class"],
)

HTTP_REQUEST_DURATION_SECONDS = _get_or_create_histogram(
    "http_request_duration_seconds",
    "HTTP request duration for normalized application routes.",
    ["route", "method", "status_class"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)

HTTP_REQUESTS_IN_FLIGHT = _get_or_create_gauge(
    "http_requests_in_flight",
    "Current number of application HTTP requests in flight.",
)

HTTP_ERRORS_TOTAL = _get_or_create_counter(
    "http_errors_total",
    "HTTP responses classified as client or server errors.",
    ["route", "method", "error_category"],
)

CELERY_TASK_EVENTS_TOTAL = _get_or_create_counter(
    "celery_task_events_total",
    "Celery task lifecycle events by bounded task type, queue, and outcome.",
    ["task_type", "queue", "outcome"],
)

CELERY_TASKS_IN_FLIGHT = _get_or_create_gauge(
    "celery_tasks_in_flight",
    "Current number of started Celery tasks in flight by bounded task type.",
    ["task_type"],
)

CELERY_TASK_DURATION_SECONDS = _get_or_create_histogram(
    "celery_task_duration_seconds",
    "Celery task execution duration by bounded task type and terminal outcome.",
    ["task_type", "outcome"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 300.0),
)

ASYNC_JOBS_TOTAL = _get_or_create_counter(
    "async_jobs_total",
    "Asynchronous job lifecycle events represented by the Celery execution boundary.",
    ["job_type", "status"],
)

ASYNC_JOB_DURATION_SECONDS = _get_or_create_histogram(
    "async_job_duration_seconds",
    "Asynchronous job execution duration by bounded job type and terminal status.",
    ["job_type", "status"],
    buckets=(0.01, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 300.0),
)

OUTBOX_EVENTS_PENDING = _get_or_create_gauge(
    "outbox_events_pending",
    "Current number of pending or expired-claim outbox events observed by the relay.",
)

OUTBOX_EVENT_OLDEST_AGE_SECONDS = _get_or_create_gauge(
    "outbox_event_oldest_age_seconds",
    "Age of the oldest pending or expired-claim outbox event observed by the relay.",
)

OUTBOX_DELIVERY_ATTEMPTS_TOTAL = _get_or_create_counter(
    "outbox_delivery_attempts_total",
    "Outbox publication attempts, including retry attempts.",
)

OUTBOX_DELIVERY_LATENCY_SECONDS = _get_or_create_histogram(
    "outbox_delivery_latency_seconds",
    "Outbox publication and state-update latency.",
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

CONVERSATION_RUN_LIFECYCLE_TOTAL = _get_or_create_counter(
    "conversation_run_lifecycle_total",
    "Conversation run lifecycle events from the durable state machine.",
    ["event"],
)

CONVERSATION_RUN_TRANSITIONS_TOTAL = _get_or_create_counter(
    "conversation_run_transitions_total",
    "Durable conversation run status transitions.",
    ["from_status", "to_status"],
)

CONVERSATION_RUN_DURATION_SECONDS = _get_or_create_histogram(
    "conversation_run_duration_seconds",
    "Duration of terminal durable conversation runs.",
    ["terminal_status"],
    buckets=(0.01, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 300.0, 900.0),
)

CONVERSATION_TERMINALS_TOTAL = _get_or_create_counter(
    "conversation_terminals_total",
    "Terminal conversation run outcomes by normalized category.",
    ["status", "category"],
)

MODEL_LOGICAL_REQUESTS_TOTAL = _get_or_create_counter(
    "model_logical_requests_total",
    "One event per logical model request after policy retries and fallback complete.",
    ["route", "outcome", "category"],
)

MODEL_LOGICAL_REQUEST_DURATION_SECONDS = _get_or_create_histogram(
    "model_logical_request_duration_seconds",
    "End-to-end duration of one logical model request after policy retries and fallback.",
    ["route", "outcome"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
)

MODEL_PROVIDER_ATTEMPTS_TOTAL = _get_or_create_counter(
    "model_provider_attempts_total",
    "One terminal event per selected provider attempt.",
    ["provider", "route", "outcome", "category"],
)

MODEL_PROVIDER_ATTEMPT_DURATION_SECONDS = _get_or_create_histogram(
    "model_provider_attempt_duration_seconds",
    "Duration of one selected provider attempt.",
    ["provider", "route", "outcome"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

MODEL_CIRCUIT_STATE = _get_or_create_gauge(
    "model_circuit_state",
    "Current observed model provider circuit state (one-hot by state).",
    ["provider", "state"],
)

MODEL_CIRCUIT_REJECTIONS_TOTAL = _get_or_create_counter(
    "model_circuit_rejections_total",
    "Model attempts rejected because the provider circuit was open or probing.",
    ["provider"],
)

DEPENDENCY_HEALTH = _get_or_create_gauge(
    "app_dependency_health",
    "Last observed application dependency health, one for healthy and zero otherwise.",
    ["component"],
)

DEPENDENCY_CHECK_DURATION_SECONDS = _get_or_create_histogram(
    "app_dependency_check_duration_seconds",
    "Duration of application dependency health checks.",
    ["component"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

DB_QUERY_DURATION_SECONDS = _get_or_create_histogram(
    "db_query_duration_seconds",
    "Aggregate database statement duration without query text or bind values.",
    ["engine", "operation"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

DB_CONNECTIONS_IN_USE = _get_or_create_gauge(
    "db_connections_in_use",
    "Current checked-out database connections by engine role.",
    ["engine"],
)

DB_CONNECTION_ERRORS_TOTAL = _get_or_create_counter(
    "db_connection_errors_total",
    "Database connection or statement errors by bounded category and engine role.",
    ["engine", "category"],
)

_SAFE_LABEL_PATTERN = re.compile(r"^[a-zA-Z0-9/][a-zA-Z0-9_.:/{}-]{0,127}$")
_HTTP_METHODS = frozenset({"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"})
_HTTP_STATUS_CLASSES = frozenset({"1xx", "2xx", "3xx", "4xx", "5xx"})
_TASK_QUEUES = frozenset({"critical", "default", "maintenance"})
_TASK_PREFIXES = frozenset(
    {
        "alerting",
        "autoheal",
        "checkpoint",
        "compliance",
        "continuous_improvement",
        "evaluation",
        "knowledge",
        "memory",
        "notifications",
        "observability",
        "prompt_effect",
        "refund",
        "shadow",
    }
)
_TASK_OUTCOMES = frozenset(
    {"accepted", "started", "succeeded", "failed", "retried", "rejected", "cancelled"}
)
_TASK_CONSUMER_OUTCOMES = frozenset(
    {"received", "succeeded", "duplicate", "retry", "terminal", "dead_lettered"}
)
_TASK_TYPES = frozenset(
    {
        "alerting.evaluate_rules",
        "alerting.check_service_health",
        "autoheal.check_celery_workers",
        "autoheal.clear_redis_cache",
        "autoheal.restart_stuck_workers",
        "autoheal.clear_expired_redis_keys",
        "autoheal.check_db_pool_health",
        "checkpoint.cleanup_old_checkpoints",
        "compliance.run_retention_daily",
        "continuous_improvement.run_weekly_audit",
        "evaluation.run_few_shot_evaluation",
        "evaluation.run_adversarial_suite",
        "knowledge.sync_document",
        "memory.extract_and_save_facts",
        "memory.prune_vector_memory",
        "memory.sync_vector",
        "notifications.send_complaint_alert",
        "notifications.send_status_update",
        "notifications.check_quality_alerts",
        "observability.log_chat_observability",
        "prompt_effect.generate_monthly_report",
        "refund.send_sms",
        "refund.process_payment",
        "refund.notify_admin",
        "shadow.run_shadow_test",
    }
)
_MODEL_OUTCOMES = frozenset({"success", "failure", "degraded", "cancelled"})
_MODEL_ATTEMPT_OUTCOMES = frozenset({"success", "failure", "cancelled"})
_FAILURE_CATEGORIES = frozenset(
    {
        "authentication",
        "rate_limit",
        "timeout",
        "connection",
        "bad_request",
        "unsupported_capability",
        "provider_unavailable",
        "invalid_response",
        "unknown",
        "none",
    }
)
_CONVERSATION_CATEGORIES = frozenset(
    {
        "completed",
        "cancelled",
        "executor_error",
        "orphaned_run",
        "tool_failed",
        "stale_run",
        "unknown",
    }
)
_DEPENDENCY_COMPONENTS = frozenset({"database", "redis", "rabbitmq", "qdrant"})
_DB_ENGINES = frozenset({"async", "sync", "unknown"})
_DB_OPERATIONS = frozenset({"SELECT", "INSERT", "UPDATE", "DELETE", "COMMIT", "OTHER"})
_DB_ERROR_CATEGORIES = frozenset({"connection", "timeout", "query", "unknown"})


def normalize_metric_label(value: object, *, fallback: str = "unknown") -> str:
    """Return a bounded label value without accepting arbitrary free text."""
    candidate = value.strip() if isinstance(value, str) else ""
    if not candidate or not _SAFE_LABEL_PATTERN.fullmatch(candidate):
        return fallback
    return candidate


def normalize_route_label(route: object | None) -> str:
    """Return a route template, never a request URL or path instance."""
    candidate = getattr(route, "path", None)
    if not isinstance(candidate, str) or not candidate.startswith("/"):
        return "unmatched"
    # A Starlette route object supplies a template. Reject common raw path values if a caller
    # accidentally passes a string-like route object from outside the routing layer.
    if re.search(r"/(?:\d{2,}|[0-9a-f]{8}-[0-9a-f-]{27,})(?:/|$)", candidate, re.IGNORECASE):
        return "unmatched"
    return normalize_metric_label(candidate, fallback="unmatched")


def normalize_http_method(method: object) -> str:
    """Return a bounded HTTP method label."""
    candidate = str(method).upper() if method is not None else ""
    return candidate if candidate in _HTTP_METHODS else "OTHER"


def http_status_class(status_code: int) -> str:
    """Return the low-cardinality class for an HTTP status code."""
    candidate = f"{status_code // 100}xx"
    return candidate if candidate in _HTTP_STATUS_CLASSES else "unknown"


def normalize_task_type(task_type: object) -> str:
    """Return a bounded task type derived from a registered task name."""
    candidate = task_type.strip() if isinstance(task_type, str) else ""
    if not candidate or len(candidate) > 128 or not _SAFE_LABEL_PATTERN.fullmatch(candidate):
        return "unknown"
    prefix = candidate.split(".", 1)[0]
    if prefix not in _TASK_PREFIXES:
        return "other"
    # Keep exact names for the finite task registry, while collapsing a future or untrusted
    # task name to its bounded subsystem instead of accepting arbitrary suffixes as labels.
    return candidate if candidate in _TASK_TYPES else prefix


def normalize_queue(queue: object) -> str:
    """Return a configured Celery queue label."""
    candidate = queue.strip() if isinstance(queue, str) else ""
    return candidate if candidate in _TASK_QUEUES else "unknown"


def normalize_model_identity(identity: object) -> str:
    """Return a bounded configured provider/model identity label."""
    return normalize_metric_label(identity, fallback="unknown")


def normalize_failure_category(category: object) -> str:
    """Return one accepted normalized failure category."""
    candidate = category.value if hasattr(category, "value") else category
    candidate_text = candidate.strip() if isinstance(candidate, str) else ""
    return candidate_text if candidate_text in _FAILURE_CATEGORIES else "unknown"


def normalize_model_outcome(outcome: object) -> str:
    """Return one logical model outcome label."""
    candidate = outcome.strip() if isinstance(outcome, str) else ""
    return candidate if candidate in _MODEL_OUTCOMES else "failure"


def normalize_model_attempt_outcome(outcome: object) -> str:
    """Return one terminal provider attempt outcome label."""
    candidate = outcome.strip() if isinstance(outcome, str) else ""
    return candidate if candidate in _MODEL_ATTEMPT_OUTCOMES else "failure"


def record_checkpoint_metrics(compressed_size: int, uncompressed_size: int, is_base: bool) -> None:
    """Record checkpoint storage metrics."""
    storage_type = "base" if is_base else "diff"
    CHECKPOINT_SIZE_BYTES.labels(storage_type=storage_type).observe(compressed_size)
    if compressed_size > 0:
        CHECKPOINT_COMPRESSION_RATIO.observe(uncompressed_size / compressed_size)


def record_outbox_publish(*, success: bool) -> None:
    """Record a low-cardinality outbox publication outcome."""
    if success:
        OUTBOX_PUBLISH_TOTAL.inc()
    else:
        OUTBOX_PUBLISH_FAILURE_TOTAL.inc()


def record_outbox_delivery_attempt() -> None:
    """Record one outbox publication attempt, including a retry."""
    OUTBOX_DELIVERY_ATTEMPTS_TOTAL.inc()


def set_outbox_backlog(*, pending: int, oldest_age_seconds: float) -> None:
    """Set aggregate outbox backlog and oldest-event age gauges."""
    OUTBOX_EVENTS_PENDING.set(max(0, pending))
    OUTBOX_EVENT_OLDEST_AGE_SECONDS.set(max(0.0, oldest_age_seconds))


def record_outbox_delivery_latency(duration_seconds: float) -> None:
    """Observe one outbox publication and state-update duration."""
    OUTBOX_DELIVERY_LATENCY_SECONDS.observe(max(0.0, duration_seconds))


def record_task_consumer(*, task_type: str, outcome: str) -> None:
    """Record a low-cardinality protected-consumer outcome."""
    normalized_outcome = outcome if outcome in _TASK_CONSUMER_OUTCOMES else "unknown"
    TASK_CONSUMER_TOTAL.labels(
        task_type=normalize_task_type(task_type),
        outcome=normalized_outcome,
    ).inc()


def record_celery_task_event(*, task_type: str, queue: str, outcome: str) -> None:
    """Record one bounded Celery task lifecycle event."""
    normalized_task = normalize_task_type(task_type)
    normalized_queue = normalize_queue(queue)
    normalized_outcome = outcome if outcome in _TASK_OUTCOMES else "failed"
    CELERY_TASK_EVENTS_TOTAL.labels(
        task_type=normalized_task,
        queue=normalized_queue,
        outcome=normalized_outcome,
    ).inc()
    ASYNC_JOBS_TOTAL.labels(
        job_type=normalized_task,
        status={
            "accepted": "pending",
            "started": "running",
            "succeeded": "completed",
            "retried": "retrying",
        }.get(normalized_outcome, normalized_outcome),
    ).inc()


def set_celery_task_in_flight(*, task_type: str, delta: int) -> None:
    """Adjust the started-task gauge without accepting task identifiers as labels."""
    CELERY_TASKS_IN_FLIGHT.labels(task_type=normalize_task_type(task_type)).inc(delta)


def record_celery_task_duration(*, task_type: str, outcome: str, duration_seconds: float) -> None:
    """Observe one bounded Celery task duration."""
    normalized_task = normalize_task_type(task_type)
    normalized_outcome = outcome if outcome in _TASK_OUTCOMES else "failed"
    duration = max(0.0, duration_seconds)
    CELERY_TASK_DURATION_SECONDS.labels(
        task_type=normalized_task,
        outcome=normalized_outcome,
    ).observe(duration)
    ASYNC_JOB_DURATION_SECONDS.labels(
        job_type=normalized_task,
        status={"succeeded": "completed", "retried": "retrying"}.get(
            normalized_outcome, normalized_outcome
        ),
    ).observe(duration)


def record_conversation_transition(*, from_status: str, to_status: str) -> None:
    """Record one existing durable conversation state transition."""
    CONVERSATION_RUN_TRANSITIONS_TOTAL.labels(
        from_status=normalize_metric_label(from_status.upper(), fallback="unknown"),
        to_status=normalize_metric_label(to_status.upper(), fallback="unknown"),
    ).inc()


def record_conversation_lifecycle(event: str) -> None:
    """Record a bounded conversation lifecycle event."""
    normalized = event.lower()
    allowed = {"started", "waiting_tool", "waiting_human", "completed", "failed", "cancelled"}
    CONVERSATION_RUN_LIFECYCLE_TOTAL.labels(
        event=normalized if normalized in allowed else "unknown"
    ).inc()


def record_conversation_duration(*, terminal_status: str, duration_seconds: float) -> None:
    """Observe the duration of one terminal conversation run."""
    normalized_status = terminal_status.upper()
    if normalized_status not in {"COMPLETED", "FAILED", "CANCELLED"}:
        normalized_status = "UNKNOWN"
    CONVERSATION_RUN_DURATION_SECONDS.labels(terminal_status=normalized_status).observe(
        max(0.0, duration_seconds)
    )


def record_conversation_terminal(*, status: str, category: str) -> None:
    """Record one terminal conversation outcome with a normalized category."""
    normalized_status = status.lower()
    if normalized_status not in {"completed", "failed", "cancelled"}:
        normalized_status = "unknown"
    normalized_category = (
        category.lower() if category.lower() in _CONVERSATION_CATEGORIES else "unknown"
    )
    CONVERSATION_TERMINALS_TOTAL.labels(
        status=normalized_status,
        category=normalized_category,
    ).inc()


def record_model_logical_request(
    *,
    route: str,
    outcome: str,
    category: str = "none",
    duration_seconds: float | None = None,
) -> None:
    """Record one logical model request, after policy retries and fallback resolve."""
    normalized_outcome = normalize_model_outcome(outcome)
    normalized_category = normalize_failure_category(category)
    normalized_route = normalize_metric_label(route, fallback="unknown")
    MODEL_LOGICAL_REQUESTS_TOTAL.labels(
        route=normalized_route,
        outcome=normalized_outcome,
        category=normalized_category if normalized_outcome == "failure" else "none",
    ).inc()
    if duration_seconds is not None:
        MODEL_LOGICAL_REQUEST_DURATION_SECONDS.labels(
            route=normalized_route,
            outcome=normalized_outcome,
        ).observe(max(0.0, duration_seconds))


def record_model_provider_attempt(
    *,
    provider: str,
    route: str,
    outcome: str,
    category: str = "none",
    duration_seconds: float | None = None,
) -> None:
    """Record one terminal selected-provider attempt with normalized failure taxonomy."""
    normalized_outcome = normalize_model_attempt_outcome(outcome)
    MODEL_PROVIDER_ATTEMPTS_TOTAL.labels(
        provider=normalize_model_identity(provider),
        route=normalize_metric_label(route, fallback="unknown"),
        outcome=normalized_outcome,
        category=normalize_failure_category(category),
    ).inc()
    if duration_seconds is not None:
        MODEL_PROVIDER_ATTEMPT_DURATION_SECONDS.labels(
            provider=normalize_model_identity(provider),
            route=normalize_metric_label(route, fallback="unknown"),
            outcome=normalized_outcome,
        ).observe(max(0.0, duration_seconds))


def set_model_circuit_state(*, provider: str, state: str) -> None:
    """Set a one-hot observed state for a configured model provider circuit."""
    normalized_provider = normalize_model_identity(provider)
    normalized_state = state.lower()
    if normalized_state not in {"closed", "open", "half_open"}:
        normalized_state = "unknown"
    for candidate_state in ("closed", "open", "half_open", "unknown"):
        MODEL_CIRCUIT_STATE.labels(
            provider=normalized_provider,
            state=candidate_state,
        ).set(1 if candidate_state == normalized_state else 0)


def record_model_circuit_rejection(*, provider: str) -> None:
    """Record one policy rejection caused by a provider circuit."""
    MODEL_CIRCUIT_REJECTIONS_TOTAL.labels(provider=normalize_model_identity(provider)).inc()


def set_dependency_health(*, component: str, healthy: bool) -> None:
    """Set the last observed health state for a bounded application dependency."""
    normalized = component.lower()
    if normalized not in _DEPENDENCY_COMPONENTS:
        normalized = "unknown"
    DEPENDENCY_HEALTH.labels(component=normalized).set(1 if healthy else 0)


def record_dependency_check_duration(*, component: str, duration_seconds: float) -> None:
    """Observe one dependency health check duration."""
    normalized = component.lower()
    if normalized not in _DEPENDENCY_COMPONENTS:
        normalized = "unknown"
    DEPENDENCY_CHECK_DURATION_SECONDS.labels(component=normalized).observe(
        max(0.0, duration_seconds)
    )


def normalize_database_engine(engine: object) -> str:
    """Return a bounded SQLAlchemy engine-role label."""
    candidate = engine.strip().lower() if isinstance(engine, str) else ""
    return candidate if candidate in _DB_ENGINES else "unknown"


def normalize_database_operation(operation: object) -> str:
    """Return a bounded SQL operation label without retaining query text."""
    candidate = operation.strip().upper() if isinstance(operation, str) else ""
    return candidate if candidate in _DB_OPERATIONS else "OTHER"


def record_database_query_duration(*, engine: str, operation: str, duration_seconds: float) -> None:
    """Observe aggregate database statement duration."""
    DB_QUERY_DURATION_SECONDS.labels(
        engine=normalize_database_engine(engine),
        operation=normalize_database_operation(operation),
    ).observe(max(0.0, duration_seconds))


def adjust_database_connections_in_use(*, engine: str, delta: int) -> None:
    """Adjust checked-out database connection count for one bounded engine role."""
    DB_CONNECTIONS_IN_USE.labels(engine=normalize_database_engine(engine)).inc(delta)


def record_database_connection_error(*, engine: str, category: str) -> None:
    """Record a database error without statement text, parameters, or exception messages."""
    normalized_category = category.strip().lower() if isinstance(category, str) else ""
    DB_CONNECTION_ERRORS_TOTAL.labels(
        engine=normalize_database_engine(engine),
        category=(
            normalized_category if normalized_category in _DB_ERROR_CATEGORIES else "unknown"
        ),
    ).inc()


def record_http_request(
    *, route: object | None, method: object, status_code: int, duration_seconds: float
) -> None:
    """Record one application HTTP request using only normalized route metadata."""
    normalized_route = normalize_route_label(route)
    normalized_method = normalize_http_method(method)
    status_class = http_status_class(status_code)
    HTTP_REQUESTS_TOTAL.labels(
        route=normalized_route,
        method=normalized_method,
        status_class=status_class,
    ).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(
        route=normalized_route,
        method=normalized_method,
        status_class=status_class,
    ).observe(max(0.0, duration_seconds))
    if status_code >= 400:
        error_category = "server_error" if status_code >= 500 else "client_error"
        HTTP_ERRORS_TOTAL.labels(
            route=normalized_route,
            method=normalized_method,
            error_category=error_category,
        ).inc()


def record_checkpoint_cleanup(count: int) -> None:
    """Record the number of checkpoints removed during cleanup."""
    CHECKPOINT_CLEANUP_TOTAL.inc(count)


def record_chat_request(
    intent_category: str | None = None,
    final_agent: str | None = None,
) -> None:
    """Increment the chat request counter."""
    CHAT_REQUESTS_TOTAL.labels(
        intent_category=intent_category or "unknown",
        final_agent=final_agent or "unknown",
    ).inc()


def record_chat_error(error_type: str) -> None:
    """Increment the chat error counter."""
    CHAT_ERRORS_TOTAL.labels(error_type=error_type).inc()


def record_chat_latency(latency_seconds: float, final_agent: str | None = None) -> None:
    """Observe chat end-to-end latency."""
    CHAT_LATENCY_SECONDS.labels(final_agent=final_agent or "unknown").observe(latency_seconds)


def record_model_attempt(*, provider: str, outcome: str) -> None:
    """Record one low-cardinality model attempt outcome."""
    MODEL_ATTEMPTS_TOTAL.labels(provider=provider, outcome=outcome).inc()


def record_model_retry(*, provider: str, category: str) -> None:
    """Record one policy retry decision."""
    MODEL_RETRIES_TOTAL.labels(provider=provider, category=category).inc()


def record_model_fallback(*, provider: str, outcome: str) -> None:
    """Record advancement from one exhausted candidate to the next."""
    MODEL_FALLBACKS_TOTAL.labels(provider=provider, outcome=outcome).inc()


def record_model_circuit_transition(*, provider: str, from_state: str, to_state: str) -> None:
    """Record a provider circuit transition without tenant/user labels."""
    MODEL_CIRCUIT_TRANSITIONS_TOTAL.labels(
        provider=provider,
        from_state=from_state,
        to_state=to_state,
    ).inc()


def record_model_degraded(*, route: str) -> None:
    """Record one explicitly configured safe static degradation."""
    MODEL_DEGRADED_TOTAL.labels(route=route).inc()


def record_node_latency(node_name: str, latency_seconds: float) -> None:
    """Observe individual node execution latency."""
    NODE_LATENCY_SECONDS.labels(node_name=node_name).observe(latency_seconds)


def record_token_usage(tokens: int, agent: str | None = None) -> None:
    """Record token consumption."""
    TOKEN_USAGE_TOTAL.labels(agent=agent or "unknown").inc(tokens)


def record_context_utilization(ratio: float) -> None:
    """Set the current context utilization ratio."""
    CONTEXT_UTILIZATION_RATIO.set(ratio)


def record_human_transfer(reason: str | None = None) -> None:
    """Increment the human transfer counter."""
    HUMAN_TRANSFERS_TOTAL.labels(reason=reason or "unknown").inc()


def record_confidence_score(score: float) -> None:
    """Observe a confidence score value."""
    CONFIDENCE_SCORE.observe(score)


def set_intent_accuracy(value: float, intent_category: str | None = None) -> None:
    """Set the intent classification accuracy gauge."""
    INTENT_ACCURACY.labels(intent_category=intent_category or "overall").set(value)


def set_rag_precision(value: float) -> None:
    """Set the RAG precision gauge."""
    RAG_PRECISION.set(value)


def set_hallucination_rate(value: float) -> None:
    """Set the hallucination rate gauge."""
    HALLUCINATION_RATE.set(value)


def record_agent_context_tokens(tokens: int, agent_name: str | None = None) -> None:
    """Record per-agent context token count after filtering."""
    AGENT_CONTEXT_TOKENS.labels(agent_name=agent_name or "unknown").set(tokens)


def record_agent_context_reduction(agent_name: str, ratio: float) -> None:
    """Record the token reduction ratio achieved by context isolation."""
    AGENT_CONTEXT_REDUCTION_RATIO.labels(agent_name=agent_name).set(ratio)


def record_redis_connection_error(error_type: str) -> None:
    """Increment the Redis connection error counter."""
    REDIS_CONNECTION_ERRORS_TOTAL.labels(error_type=error_type).inc()


def record_redis_operation_latency(operation: str, latency_seconds: float) -> None:
    """Observe Redis operation latency."""
    REDIS_OPERATION_LATENCY_SECONDS.labels(operation=operation).observe(latency_seconds)


def set_redis_connections_active(count: int) -> None:
    """Set the number of active Redis connections."""
    REDIS_CONNECTIONS_ACTIVE.set(count)


def set_cache_hit_ratio(cache_name: str, ratio: float) -> None:
    """Set the cache hit ratio for a named cache."""
    REDIS_CACHE_HIT_RATIO.labels(cache_name=cache_name).set(ratio)


def record_answer_correctness(agent_type: str, score: float) -> None:
    """Set the answer correctness gauge for an agent type."""
    ANSWER_CORRECTNESS.labels(agent_type=agent_type).set(score)


def observe_agent_latency(agent_type: str, duration: float) -> None:
    """Observe agent execution latency in seconds."""
    AGENT_LATENCY_SECONDS.labels(agent_type=agent_type).observe(duration)


def set_token_efficiency(agent: str, ratio: float) -> None:
    """Set the token efficiency ratio for an agent."""
    TOKEN_EFFICIENCY.labels(agent=agent).set(ratio)


def record_tokens_total(count: int) -> None:
    """Increment the total tokens consumed counter."""
    TOKENS_TOTAL.inc(count)


def record_cache_hit(cache_name: str) -> None:
    """Increment the cache hits counter for a named cache."""
    CACHE_HITS_TOTAL.labels(cache_name=cache_name).inc()


def record_cache_miss(cache_name: str) -> None:
    """Increment the cache misses counter for a named cache."""
    CACHE_MISSES_TOTAL.labels(cache_name=cache_name).inc()


def record_high_cost_request(agent: str) -> None:
    """Increment the high cost requests counter for an agent."""
    HIGH_COST_REQUESTS_TOTAL.labels(agent=agent).inc()


def record_safety_block(layer: str, reason: str) -> None:
    """Increment the safety blocks counter with layer and reason labels."""
    SAFETY_BLOCKS_TOTAL.labels(layer=layer, reason=reason).inc()


def record_pii_detection(pii_type: str, source: str) -> None:
    """Increment the PII detections counter by type and source."""
    PII_DETECTIONS_TOTAL.labels(pii_type=pii_type, source=source).inc()


def record_injection_attempt() -> None:
    INJECTION_ATTEMPTS_TOTAL.inc()


def record_pii_breach(pii_type: str) -> None:
    PII_BREACHES_TOTAL.labels(pii_type=pii_type).inc()


def record_injection_bypassed() -> None:
    INJECTION_BYPASSED_TOTAL.inc()


def record_safety_check(layer: str) -> None:
    SAFETY_CHECKS_TOTAL.labels(layer=layer).inc()


def record_rate_limit_hit(limit_type: str) -> None:
    """Increment the rate limit hits counter by limit type."""
    RATE_LIMIT_HITS_TOTAL.labels(limit_type=limit_type).inc()


def record_web_vital(metric: str, value: float, rating: str) -> None:
    if metric == "LCP":
        WEB_VITALS_LCP.labels(rating=rating).observe(value)
    elif metric == "CLS":
        WEB_VITALS_CLS.labels(rating=rating).observe(value)
    elif metric == "FID":
        WEB_VITALS_FID.labels(rating=rating).observe(value)
    elif metric == "FCP":
        WEB_VITALS_FCP.labels(rating=rating).observe(value)
    elif metric == "TTFB":
        WEB_VITALS_TTFB.labels(rating=rating).observe(value)


def get_metrics_response() -> tuple[bytes, str]:
    """Generate the latest Prometheus metrics payload."""
    return generate_latest(), CONTENT_TYPE_LATEST
