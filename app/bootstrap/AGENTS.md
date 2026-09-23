# AGENTS.md - Local Bootstrap

Read the repository root [`AGENTS.md`](../../AGENTS.md) first.

This package owns the development-only, idempotent reconciliation of persisted local/UAT data.

## Contract

- `scripts/bootstrap_local_data.py` is the only canonical entry point.
- Refuse `ENVIRONMENT=production` and require `LOCAL_BOOTSTRAP_ENABLED=true`.
- Read identity/password inputs only through `app.core.config.settings`; never log secrets.
- Use current tenant-aware models, source-object storage, retrieval ingestion, and outbox APIs.
- Keep PostgreSQL authoritative, Qdrant derived, Redis ephemeral, and RabbitMQ transport-only.
- Re-running the bootstrap must reconcile stable natural keys without duplicate rows or vectors.
- Do not delete, truncate, recreate schemas, weaken RLS, or remove existing developer data.
- Synthetic records must be clearly local/UAT data and must not resemble real customer PII.

## Verification

```bash
uv run pytest tests/bootstrap/ tests/test_initialize_vector_data.py tests/test_docker_startup.py
uv run ruff check app/bootstrap tests/bootstrap
uv run ty check --error-on-warning app/bootstrap scripts/bootstrap_local_data.py scripts/verify_local_stack.py
```

Use only an explicitly isolated `test_` database or disposable Compose project for empty-state or destructive acceptance.
