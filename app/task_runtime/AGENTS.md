# AGENTS.md - Task Runtime

> **IMPORTANT**: Read the root [`AGENTS.md`](../../AGENTS.md) and the architecture guardrails before changing this package.

## Responsibility

This package owns versioned execution metadata, JSON envelopes, typed task payloads, the best-effort direct-dispatch adapter, worker binding lifecycle, protected-consumer receipt orchestration, retry classification, and terminal-message publication. Receipt orchestration supports both transactionally atomic database effects and stable/idempotent external projections with a committed recoverable lease. It does not own outbox persistence, relay behavior, queue declarations, or business handlers.

## Invariants

- Tenant tasks require an explicit validated `tenant_id`; never infer one from a worker default.
- Business payload stays separate from execution metadata and contains only sanitized/minimal data.
- Bind tenant, correlation, and OpenTelemetry context before handler I/O; always reset them in `finally`.
- Protected database-local handlers run their effect and completed receipt in one transaction; completed duplicates return the stored result without replaying the effect.
- External effects remain at-least-once unless their provider honors the propagated stable idempotency key; never claim global exactly-once.
- A stale `PROCESSING` lease is reclaimable. A terminal message is acknowledged only after its sanitized identity and failure evidence reaches RabbitMQ's DLQ.
- `dispatch_task` remains direct Celery publication only for classified best-effort or non-transactional work. Critical business side effects enqueue through `app.outbox`.
- System/global schedules use `SystemTaskContext`; they never impersonate a default tenant.
- Tenant queues run with the PostgreSQL runtime capability. The maintenance queue is a separate
  process using the maintenance database capability; a bound tenant still narrows its RLS view.

## Verification

```bash
uv run pytest tests/task_runtime/
uv run ruff check app/task_runtime tests/task_runtime
uv run ty check --error-on-warning app/task_runtime tests/task_runtime
```
