# AGENTS.md - Compliance

Read the root `AGENTS.md` first. This package owns data classification, retention policy,
append-only compliance evidence, and exact-operation approval policy.

- Keep the dataset registry complete for every production SQLModel table and external data store.
- Retention must be tenant-scoped, predicate-bound, batch-limited, retry-safe, and dry-runnable.
- Audit metadata is minimal and sanitized; never store credentials, tokens, cookies, or exported data.
- Sensitive approvals are tenant-bound, parameter-bound, expiring, single-use, and require a
  different currently authorized approver.
- Compliance controls are engineering controls, not legal or certification claims.

Verify with targeted tests under `tests/compliance/` and scoped Ruff/ty checks.
