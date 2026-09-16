# Observability Runbook

This runbook is for the low-cardinality application signals provisioned by T17. It complements
the compliance and incident runbooks; it is not an authorization or audit-data access procedure.

## API error rate or latency

- **Symptom:** `APIHigh5xxRate` or `APIHighP95Latency` is firing, or users report slow/failed
  requests.
- **Inspect:** Grafana **Platform / API Health**; review dependency health, database query p95,
  and `db_connections_in_use`; then filter Loki by `service`, `level`, and the `correlation_id`
  from a representative response. Open the matching trace in Tempo using `trace_id`. Use the
  normalized `route` field, never a concrete URL, for aggregation.
- **Likely causes:** application exception, database pool/query or connection degradation,
  Redis/Qdrant degradation, or model-provider latency. Distinguish `4xx` client traffic from `5xx`
  server failures before escalating.
- **Safe first actions:** compare the error/latency window with dependency health and recent
  configuration changes; check worker and model-provider panels; temporarily reduce diagnostic
  verbosity if logs are noisy. Do not copy request bodies, cookies, or authorization headers into
  tickets.
- **Escalate:** page the service owner when the alert remains firing after the configured `for`
  period or dependency health is zero; include alert name, time window, route template, and a
  redacted correlation/trace ID.

## Worker, async, or outbox delivery

- **Symptom:** `AsyncTaskFailureSpike`, `OutboxPublishFailureSpike`, `OutboxBacklogHigh`, or
  `OutboxOldestEventStale` is firing.
- **Inspect:** Grafana **Async / Outbox / Worker** for task outcome, in-flight count, backlog, age,
  and delivery attempts. Follow an outbox `trace_id` to the relay span and then the worker span;
  inspect the sanitized `error_type`/`failure_code` fields.
- **Likely causes:** RabbitMQ unavailable, a maintenance/critical worker stopped, lease expiry,
  a rejected envelope, or a downstream dependency failure. A growing attempt count with a stable
  backlog indicates retry pressure rather than a successful drain.
- **Safe first actions:** verify the relevant queue and service health, check that the intended
  worker role is running, and allow the bounded retry policy to drain after a transient recovery.
  Do not publish directly to the broker, edit outbox rows, bypass tenant isolation, or delete a
  dead-letter record as a first response.
- **Escalate:** involve the delivery owner if the oldest-event age continues to grow, publication
  failures persist, or a critical queue is unavailable. Preserve the event/task identifiers only
  in the restricted incident system.

## Model provider, fallback, or circuit

- **Symptom:** `ModelProviderFailureSpike`, `ModelFallbackSpike`, or `ModelCircuitOpen` is firing;
  AI responses are degraded or unavailable.
- **Inspect:** Grafana **AI / Conversation Runtime**. Compare
  `model_logical_requests_total` with `model_provider_attempts_total`: one logical request may
  legitimately have multiple bounded attempts. Check normalized categories such as `timeout`,
  `rate_limit`, `connection`, `authentication`, and `invalid_response`.
- **Likely causes:** provider outage/rate limiting, invalid deployment configuration, or a circuit
  protecting the provider after repeated transient failures.
- **Safe first actions:** verify provider status and configured logical route/model identity,
  confirm fallback traffic is bounded, and wait for the half-open probe window. Do not expose or
  rotate credentials from Grafana, paste prompts/completions into logs, or mutate breaker state
  through monitoring tools.
- **Escalate:** contact the model-platform owner when the circuit remains open beyond the alert
  window, all candidates fail, or logical failures continue after provider recovery.

## Conversation runtime failure

- **Symptom:** `ConversationFailureSpike` is firing or terminal failures/cancellations increase.
- **Inspect:** `conversation_run_lifecycle_total`, `conversation_run_transitions_total`, and the
  run's trace/log correlation. Confirm whether the terminal category is `executor_error`,
  `tool_failed`, `orphaned_run`, `stale_run`, or `cancelled`.
- **Safe first actions:** verify the transition sequence and tool/model dependency signals. Retry
  only through the existing application contract; do not edit runtime rows or replay a run by
  hand.
- **Escalate:** involve the conversation-runtime owner if terminal uniqueness is violated, runs
  remain non-terminal past their lease, or failures are not explained by a dependency alert.

## Telemetry degradation

If a collector/backend is unavailable, business requests and task delivery remain authoritative.
Check collector health, bounded queue/back-pressure indicators, and local application stderr. A
missing metric, log, or trace is an evidence gap—not permission to weaken authentication, RLS, or
audit controls. Restore the telemetry path and record the gap in the incident timeline.
