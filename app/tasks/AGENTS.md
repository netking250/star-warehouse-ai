# AGENTS.md - Tasks

> **IMPORTANT**: Read the root [`AGENTS.md`](../../AGENTS.md) first for repo-wide rules.

## Maintenance Contract

- This file is a living document for Celery async tasks.
- Update this file in the same PR when adding new tasks or changing task conventions.

## Read Order

1. Read the root [`AGENTS.md`](../../AGENTS.md) for repo-wide rules, commands, and routing.
2. Read this file for task-specific guidance.
3. Read [`docs/explanation/architecture/task-runtime.md`](../../docs/explanation/architecture/task-runtime.md) before changing request-sourced task signatures or dispatch.

## Overview

Celery async task layer for background processing. Tasks are triggered by graph nodes and services to perform non-blocking operations like fact extraction, notifications, knowledge sync, and evaluation.

## Key Files

| Role | File | Notes |
|------|------|-------|
| Alert evaluation | `@app/tasks/alert_tasks.py` | Evaluate alert rules and check service health |
| Autoheal orchestration | `@app/tasks/autoheal.py` | Self-healing orchestration module for system health |
| Autoheal tasks | `@app/tasks/autoheal_tasks.py` | Restart stuck workers, clear expired Redis keys, check DB pool health |
| Checkpoint cleanup | `@app/tasks/checkpoint_tasks.py` | Cleanup old LangGraph checkpoints from Redis (max 100 per thread) |
| Compliance retention | `@app/tasks/compliance_tasks.py` | Daily maintenance-only tenant and record-bounded retention pass |
| Memory tasks | `@app/tasks/memory_tasks.py` | Async fact extraction, reliable structured-memory vector projection, and vector pruning |
| Notifications | `@app/tasks/notifications.py` | Email/SMS notification sending |
| Observability logging | `@app/tasks/observability_tasks.py` | Post-chat async observability logging to keep SSE critical path fast |
| Knowledge tasks | `@app/tasks/knowledge_tasks.py` | Knowledge base sync and embedding |
| Refund tasks | `@app/tasks/refund_tasks.py` | Refund processing workflows |
| Evaluation tasks | `@app/tasks/evaluation_tasks.py` | Async evaluation runs |
| Continuous improvement | `@app/tasks/continuous_improvement_tasks.py` | CI pipeline tasks |
| Prompt effect tracking | `@app/tasks/prompt_effect_tasks.py` | Prompt A/B effect measurement |
| Shadow testing | `@app/tasks/shadow_tasks.py` | Shadow mode testing tasks |
| Tracing setup | `@app/celery_tracing.py` | Celery LangSmith bootstrap kept outside the task package to avoid import cycles |

## Commands

```bash
# Run task module tests
uv run pytest tests/tasks/

# Start Celery worker (recommended: auto-waits for dependencies)
./start_worker.sh

# Manual tenant worker, maintenance worker, and scheduler
uv run celery -A app.celery_app worker --loglevel=info --concurrency=4 --pool=solo --queues=critical,default
DB_CAPABILITY=maintenance uv run celery -A app.celery_app worker --loglevel=info --concurrency=2 --pool=solo --queues=maintenance
uv run celery -A app.celery_app beat --loglevel=info
```

## Code Style

General Python rules are defined in the root `AGENTS.md`. Task-specific conventions:

- **Type hints**: All Celery task functions must have complete type annotations.
- **Docstrings**: Google-style docstrings for all tasks explaining purpose and parameters.
- **Error handling**: Tasks must handle failures gracefully and retry with exponential backoff.
- **Idempotency**: Critical database-local handlers use `consume_db_task`; the effect and completed receipt share one transaction and completed duplicates do not rerun it.

## Testing Patterns

- Mock the centralized `dispatch_task` seam or a task's `apply_async` in unit tests.
- Test task logic independently of Celery infrastructure.
- Verify retry behavior with mocked failures.
- Test task chaining and dependency resolution.

## Conventions

- **Celery bootstrap boundary**: Keep helpers imported by `@app/celery_app.py` outside
  `@app/tasks/`; importing a task submodule executes `app.tasks.__init__` and can create a
  circular import before the Celery application exists.
- **Async triggers**: Critical request callers persist a typed envelope through `@app/outbox/`; best-effort or non-transactional callers use `@app/task_runtime/dispatch.py`. Direct `.delay()`/`.apply_async()` outside infrastructure adapters is forbidden.
- **Worker context**: Tenant tasks accept a versioned envelope, revalidate tenant existence/status, enter `task_execution_scope`, and perform I/O only while the resolved tenant/trace/correlation context is bound.
- **Knowledge source objects**: Knowledge task envelopes carry document identity only. Workers load
  the persisted logical object key and resolve bytes through `@app/storage/`; never open an
  API-container-local path as the durable task contract.
- **Knowledge vectors**: Knowledge sync runs in-process inside the task scope so Qdrant writes and replacement deletes retain the resolved tenant boundary; do not launch a context-free ETL subprocess.
- **Sanitized payloads**: Telemetry, evaluation, usage, and memory tasks accept redacted/minimal data only. Recipient PII needed by a delivery adapter must not be logged or returned.
- **Memory projection**: `memory.sync_vector` reloads authoritative content from PostgreSQL using the envelope identity. Its broker payload contains only memory ID, version, and operation; external execution uses the shared receipt lease and a stable Qdrant point ID.
- **System tasks**: Global schedules use explicit system scope; never synthesize or inherit a default tenant.
- **Maintenance database capability**: Beat/global database tasks run on the separately deployed
  maintenance queue/worker. If a task receives a tenant `TaskContext`, PostgreSQL RLS still narrows
  the maintenance session to that tenant; application RBAC never chooses database capability.
- **Reliable critical tasks**: Use per-task late ACK, worker-loss rejection, `acks_on_failure_or_timeout=False`, bounded classified retries, and terminal DLQ publication. Do not apply these policies blindly to every task.
- **Async database loops**: A task entered through `async_to_sync` must create and dispose its
  async SQLAlchemy engine inside that invocation; never reuse the web process's pooled async engine.
- **Task naming**: Use descriptive task names: `<module>.<task_name>`.
- **Result storage**: Protected critical tasks ignore the Celery result backend and retain outcomes in durable receipts; other result-bearing tasks may continue to use Redis.
- **Model seam**: Evaluation/shadow workers construct gateway clients by route alias. Provider
  retries and automatic fallback are not task-local policy and remain outside T13.
- **Max retries**: Set reasonable max retries (3-5) with exponential backoff (2^n seconds).

## Anti-Patterns

- **Synchronous LLM calls in tasks**: While tasks run in background, avoid blocking the worker with long LLM calls; use timeouts.
- **Database locks in tasks**: Avoid long-running transactions that hold database locks.
- **Missing error handling**: Always handle exceptions in tasks to prevent worker crashes.

## Related Files

- `@app/celery_app.py` — Celery application configuration.
- `@app/memory/extractor.py` — Fact extraction triggered by memory tasks.
- `@app/memory/summarizer.py` — Session summarization triggered from graph nodes.
