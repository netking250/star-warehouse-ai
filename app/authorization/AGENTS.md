# AGENTS.md - Authorization

> **IMPORTANT**: Read the root [`AGENTS.md`](../../AGENTS.md) first for repo-wide rules.

## Scope

This package owns application roles, capability scopes, current tenant-membership resolution,
policy decisions, and the explicit HTTP/WebSocket route inventory.

## Invariants

- Resolve effective authority from current local tenant authorization state; JWT and OIDC role or
  scope claims are never the sole authority.
- Require an active tenant-owned user record before granting any tenant capability.
- Keep application `SUPER_ADMIN` separate from PostgreSQL roles and RLS capabilities.
- Add every production HTTP or WebSocket endpoint to `route_inventory.py`; unclassified routes
  must fail the structural guard.
- Keep policy failures non-sensitive at the transport boundary and structured in security logs.
- Authorization mutations and audit evidence share one caller-owned database transaction.
