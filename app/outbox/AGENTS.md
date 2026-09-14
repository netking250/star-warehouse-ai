# AGENTS.md - Transactional Outbox

> **IMPORTANT**: Read the root [`AGENTS.md`](../../AGENTS.md), architecture guardrails, and task-runtime architecture before changing this package.

## Responsibility

This package owns transactional enqueue, relay claiming/retry, and the task publisher Port plus current Celery adapter. It does not own broker topology, consumer deduplication, DLQ policy, or business handlers.

## Invariants

- `enqueue_task` receives the caller's `AsyncSession`, flushes, and never commits or rolls back.
- Persist only a validated tenant `TaskEnvelope` with sanitized/minimal payload; raw recipient or request PII is rejected.
- The relay scans the operational cross-tenant table, claims with `FOR UPDATE SKIP LOCKED` and a recovery lease, commits the claim, then publishes outside the database transaction.
- Publication is at-least-once. A successful publish followed by a failed state update can be retried with the same idempotency key.
- Only the publisher adapter knows Celery. Business services depend on the outbox interface and task-name strings.
- Do not add RabbitMQ, a DLQ, consumer inbox/deduplication, or T04 behavior here during T03.

## Verification

```bash
uv run pytest tests/outbox/
uv run ruff check app/outbox app/models/outbox.py tests/outbox
uv run ty check --error-on-warning app/outbox app/models/outbox.py tests/outbox
```
