# Trusted Request / Task Context

T02 introduces one request-to-worker contract for tenant-scoped background work. It is an application seam inside the modular monolith, not a new deployment service and not a reliable-delivery claim.

## Contracts

`AuthContext` is the trusted HTTP request source. A caller converts it into a frozen `TaskContext` containing `tenant_id`, `user_id`, `correlation_id`, optional OpenTelemetry `trace_id` and carrier, a deterministic `idempotency_key`, and an optional conversation `thread_id`. A missing tenant, user, correlation identity, invalid trace, or unknown field fails validation; a tenant is never inferred in a worker.

`TaskEnvelope` is the versioned JSON message:

```text
schema_version
task_context
payload
```

Execution metadata and business payload are separate. Each handler validates its own typed payload before I/O. T03 preserves this envelope while routing critical refund/order and knowledge-sync intent through `app.outbox`; classified best-effort and non-transactional work continues through `app.task_runtime.dispatch.dispatch_task`.

Global Beat work uses `SystemTaskContext`/`SystemTaskEnvelope`. It has an explicit `system` scope and no tenant/user identity; it never impersonates a default tenant. Every configured Beat entry supplies this envelope, and maintenance compatibility handlers validate and bind it when invoked by the scheduler.

## Binding Lifecycle

```text
deserialize envelope
→ validate TaskContext and typed payload
→ extract existing OpenTelemetry carrier
→ bind tenant + correlation + execution context
→ start a task span with task/idempotency/tenant linkage
→ execute handler I/O
→ finally detach trace and reset every ContextVar
```

The `finally` cleanup is mandatory because a Celery worker process handles sequential tasks. A malformed tenant envelope fails before handler I/O. System task binding deliberately does not create a tenant identity.

## Sanitized Payload Rule

PII filtering is a one-way boundary for telemetry, observability, evaluation, usage, and memory extraction. These task payloads receive the redacted question/answer/history or smaller structured metadata and validate that supported raw PII is absent. They must never reload the original `chat_request.question` after filtering. Outbox payloads reject raw recipient/request fields and detected PII. A delivery worker may resolve minimum recipient data from tenant-scoped storage, but must not copy it into the envelope, logs, or task results.

## Trace and Idempotency

The existing OpenTelemetry carrier is injected at dispatch and extracted at worker entry; the worker creates a child span and binds the existing structured-log correlation ID. No user or conversation identifier is added as an unbounded metrics label.

The idempotency key is a stable SHA-256 identity derived from task name and trusted execution identifiers, never from raw payload or process-random state. T04 uses this identity with tenant and handler to suppress completed duplicates for protected critical database handlers.

## Current Delivery Semantics

Critical migrated writes use an atomic business transaction plus outbox row. The relay publishes through Celery with RabbitMQ as broker and at-least-once semantics; duplicate publication is possible when broker success precedes a failed `PUBLISHED` update. Protected database-local handlers are duplicate-safe through durable receipts, while global exactly-once is not claimed. See [Reliable Celery](reliable-celery.md).

`dispatch_task` still calls Celery directly for classified best-effort telemetry, deferred T05 memory work, system schedules, and explicit non-transactional commands. Those paths do not gain transactional durability from T03.

## Verification Seams

T03 adds transaction rollback/commit, relay recovery/failure/concurrency, tenant/PII preservation, and duplicate-window tests around the same envelope contract.

Tests cover JSON round-trip and schema versioning, missing-tenant rejection at a real worker entry point, tenant/correlation/trace binding, cleanup and sequential-task isolation, stable idempotency propagation, direct-publication prevention outside the dispatch seam, and an HTTP → envelope → worker → database regression proving that supported raw PII is absent from both task messages and observability/token-usage records.
