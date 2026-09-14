# Transactional Outbox

T03 makes critical business state and the fact that required asynchronous work must occur atomic in PostgreSQL. T04 changes the publisher adapter's Celery transport to RabbitMQ without changing business services or the outbox Port.

## Ownership and Flow

```text
caller-owned database transaction
  ├─ business record / audit
  └─ sanitized TaskEnvelope in outbox_events
commit
  ↓
independent Outbox Relay
  ↓
TaskPublisher Port
  ↓
current Celery adapter and broker
```

The business use case owns commit and rollback. `enqueue_task(session=...)` uses that exact `AsyncSession`, validates tenant and payload safety, flushes the event, and never commits or rolls back. Business services do not import Celery tasks or publish to a broker.

The relay is an independent runtime role started with:

```bash
uv run python -m app.outbox
```

It supports bounded batch size, configurable polling and lease duration, structured logs, OpenTelemetry spans, low-cardinality success/failure counters, and SIGINT/SIGTERM shutdown.

## Relay Claim and Recovery

Each relay pass uses `SELECT ... FOR UPDATE SKIP LOCKED` to claim eligible rows. The short claim transaction changes each row to `PUBLISHING`, records a unique claim token and lease expiry, increments `attempt_count`, and commits before broker I/O. Slow broker publication therefore does not hold row locks or an open business transaction.

Only the relay holding the matching claim token may record the result. A failed publish returns the row to `PENDING`, records a bounded error string, and advances `available_at` with bounded exponential backoff. If a relay crashes while a row is `PUBLISHING`, the expired lease makes it eligible for another relay.

## Delivery Semantics

- Business data plus outbox row: atomic transactional write.
- Outbox to broker: at-least-once.
- Exactly-once: not claimed.

If broker publication succeeds and the process dies before `PUBLISHED` is committed, the row remains recoverable and may be published again after the lease expires. The same task envelope and idempotency key are retained so protected T04 consumers can deduplicate completed work. This duplicate window is deliberate and is not hidden by marking before publish; global exactly-once is not claimed.

## Tenant and PII Rules

`outbox_events.tenant_id` has no model or database default. Enqueue fails when the active transaction tenant and `TaskContext.tenant_id` differ. The stored JSON is the T02 `TaskEnvelope`; raw request fields and detected unredacted PII are rejected.

Refund SMS events persist only `refund_id`. The worker resolves the recipient inside its validated tenant scope, so phone numbers are not stored in the outbox or emitted in logs/results.

The table is an operational cross-tenant relay table rather than a tenant-owned business model. Relay reads are global by design; tenant integrity is enforced at the only application write interface and preserved in every published envelope.

## Migrated and Classified Calls

| Call path | Classification | T03 behavior |
| --- | --- | --- |
| Refund application → risk audit notification | Critical business side effect | Same transaction + outbox |
| Admin approval → refund payment | Critical business side effect | Same transaction + outbox |
| Admin approval → refund SMS | Required workflow notification | Same transaction + PII-free outbox reference |
| Knowledge document create/resync → indexing | Required state transition | Same transaction + outbox |
| Chat observability and token/evaluation logging | Best-effort telemetry | Direct task-runtime dispatch remains |
| Memory extraction | Deferred to T05 consistency work | Direct task-runtime dispatch remains |
| Complaint emails | Best-effort operator notification | Direct task-runtime dispatch remains |
| Manual evaluation, shadow tests, prompt reports | Explicit non-transactional command | Direct task-runtime dispatch remains |
| Beat/maintenance tasks | System/scheduled task | Existing scheduler dispatch remains |

This classification avoids treating metrics and logs as business facts while closing the confirmed post-commit loss windows.
