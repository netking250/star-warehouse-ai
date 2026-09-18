# AGENTS.md - Storage

> **IMPORTANT**: Read the root [`AGENTS.md`](../../AGENTS.md) first for repo-wide rules.

## Scope

This package owns stable source-object identifiers and storage adapters. It does not own derived
Qdrant data or database metadata.

## Invariants

- Persist tenant-scoped logical object keys, never host-specific or container-local absolute paths.
- Validate the active tenant namespace on every read and delete.
- API and worker processes must resolve keys through the same canonical adapter and configured root.
- The local filesystem adapter is for local/demo use. Do not represent its Compose named volume as
  production-durable object storage.
- A production S3-compatible implementation requires a reviewed adapter and explicit operational
  recovery evidence before it can be described as active.

## Verification

```bash
uv run pytest tests/storage/ tests/tasks/test_knowledge_ingestion_storage.py
```
