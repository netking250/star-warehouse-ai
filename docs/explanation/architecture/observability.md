# Observability Architecture

T17 keeps signal ownership explicit across the modular-monolith runtime:

| Signal | Producer | Local storage/query path | Responsibility |
| --- | --- | --- | --- |
| Metrics | API middleware, SQLAlchemy engine/pool hooks, Celery signals, outbox relay, conversation runtime, model failure policy, health checks | Prometheus scrape, remote-write to Mimir, Grafana PromQL | Aggregate health, latency, throughput, and failure trends |
| Logs | Python structured logger on API/worker/scheduler/outbox | stdout, Promtail, Loki | Safe diagnostic events and correlation drill-down |
| Traces | OpenTelemetry SDK/instrumentors plus explicit outbox/model spans | OTel Collector, Tempo, Grafana TraceQL | Request/workflow causality and latency |
| Audit | T11 compliance/authorization stores | PostgreSQL audit tables | Immutable security and business evidence; not a metrics or log sink |

## Bounded dimensions

Application metrics use route templates, HTTP method/status class, configured task names from the
finite registry (or a subsystem fallback), queue, normalized failure category, logical provider
identity, lifecycle state, and dependency component. Tenant, user, request, correlation,
conversation, run, task ID/payload, prompt, raw URL, and exception-message values are not
Prometheus labels. Tenant and individual execution identifiers remain available only in restricted
structured logs/traces where the existing T02/T11 contracts permit them.

Database telemetry is aggregate-only: engine role, SQL verb, pool connections in use, and one of
the normalized connection/timeout/query error categories. SQL text and bind values are never
logged, labeled, or exported as metric dimensions.

Logs are JSON in the Compose runtime by default. The central logging filter recursively redacts
authorization/cookie/CSRF credentials, API keys, passwords, token fields, and request/response
body fields. Provider failures are represented by normalized categories and bounded error types;
raw provider payloads are not recorded in manual spans or application logs.

## Correlation and async handoff

Inbound HTTP accepts a bounded diagnostic `X-Correlation-ID` or generates one. OpenTelemetry uses
the W3C trace-context propagator. T02 `TaskContext.trace_context` is the only serialized trace
carrier across direct task or transactional-outbox handoff; runtime OpenTelemetry objects are
never put in a `TaskEnvelope`. The relay extracts that carrier, creates an `outbox.publish` span,
and Celery/worker instrumentation creates the downstream task span. Long-lived work is therefore
linked by the accepted carrier without pretending that broker delay is synchronous request time.

## Local topology

Start `docker-compose.monitoring.yml` alongside the application Compose project. Prometheus pulls
`/metrics` from the API and remote-writes Mimir. Promtail ships Docker stdout to Loki. The OTel
Collector accepts OTLP traces on loopback-only development ports and forwards them to Tempo. The
Collector intentionally does not also receive Prometheus metrics or logs, avoiding duplicate
pipelines and collector self-ingestion.

The provisioned operational dashboards are deliberately small:

- `t17-platform-health`: request rate, 5xx rate, p95 latency, in-flight work, dependencies.
- `t17-async-delivery`: task lifecycle/failure, in-flight work, outbox backlog/age, delivery.
- `t17-ai-runtime`: logical model traffic, provider attempts, fallback, circuit, conversations.

Grafana's local/demo contact points are loopback no-op webhooks. External email, Slack, PagerDuty,
and webhook credentials are deployment concerns and must be injected outside the repository.
