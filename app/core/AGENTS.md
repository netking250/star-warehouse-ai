# AGENTS.md - Core

> **IMPORTANT**: Read the root [`AGENTS.md`](../../AGENTS.md) first for repo-wide rules.

## Maintenance Contract

- This file is a living document for core infrastructure.
- Update this file in the same PR when adding new core utilities or changing infrastructure conventions.

## Read Order

1. Read the root [`AGENTS.md`](../../AGENTS.md) for repo-wide rules, commands, and routing.
2. Read this file for core-specific guidance.

## Overview

Core infrastructure and cross-cutting concerns: configuration, security, database, Redis, LLM factory, tracing, logging, rate limiting, and email.

## Key Files

| Role | File | Notes |
|------|------|-------|
| Cache | `@app/core/cache.py` | `CacheManager` with 7 cache types (intent, profile, retrieval, facts, preferences, summaries, vector_search) + Redis connection pooling + circuit breaker + Prometheus metrics |
| Branding | `@app/core/branding.py` | Canonical product identity, service slug, version, and v5 legacy-name normalization |
| Configuration | `@app/core/config.py` | `Settings` with nested `ConfidenceSettings`, bounded outbox settings, and generic OIDC provider settings; single source of truth for env vars. Uses `_create_settings()` factory to avoid top-level instantiation errors during static analysis |
| Security | `@app/core/security.py` | JWT authentication adapters, current-membership resolution, HTTP/WS policy dependencies, and token/session revocation |
| Browser session | `@app/core/browser_session.py` | Host-only auth cookie, signed session-bound CSRF, and exact trusted-origin validation |
| Tenancy | `@app/core/tenancy.py` | Fail-closed tenant context plus Redis, Qdrant, and storage namespace primitives |
| Tenant resolver | `@app/core/tenant_resolver.py` | Tenant existence/status validation for request and worker boundaries |
| Database | `@app/core/database.py` | Async/sync session makers, application tenant guards, and centralized transaction-local RLS binding |
| PostgreSQL RLS | `@app/core/rls.py` | Canonical `app.current_tenant_id`, fixed capability roles, and fail-closed transaction binding |
| Database role provisioning | `@app/core/database_roles.py` | Creates/hardens configured login roles from secrets and grants non-login runtime/maintenance capabilities |
| Redis | `@app/core/redis.py` | Redis client creation and connection pooling |
| LLM compatibility factory | `@app/core/llm_factory.py` | Legacy names returning the canonical gateway-backed client; never constructs provider SDK objects |
| Structured logging | `@app/core/structured_logging.py` | `JsonFormatter` with trace_id/span_id/correlation_id support, Filebeat/Fluentd integration |
| Tracing | `@app/core/tracing.py` | OpenTelemetry/LangSmith tracing configuration |
| Logging | `@app/core/logging.py` | Structured logging with correlation ID support |
| Email | `@app/core/email.py` | Email sending utilities |
| Rate limiting | `@app/core/limiter.py`, `@app/core/slowapi.env` | Request rate limiting configuration; SlowAPI reads its dedicated ASCII config so it does not reparse the UTF-8 application `.env` with Starlette defaults. |
| Utilities | `@app/core/utils.py` | General utilities (`utc_now`, `build_thread_id`, `clamp_score`, etc.) |

## Commands

```bash
# Run core tests
uv run pytest tests/core/
```

## Code Style

General Python rules are defined in the root `AGENTS.md`. Core-specific conventions:

- **Type hints**: All core utilities must be fully typed.
- **Async**: All I/O utilities (database, Redis, email) must be async.
- **Configuration**: All settings centralized in `config.py`; never read `os.environ` outside this file.
- **Cross-cutting**: Core modules are imported by many other modules; keep them stable and backward-compatible.

## Testing Patterns

- Mock external dependencies (database, Redis, email) in core tests.
- Test configuration loading with different environment variable sets.
- Verify security utilities (JWT, password hashing) with known inputs.

## Conventions

- **Settings singleton**: Access settings via `app.core.config.settings`.
- **Brand identity**: Import stable product constants from `branding.py`; do not duplicate names or versions in runtime code.
- **Settings factory**: `_create_settings()` wraps `Settings()` instantiation to defer runtime env-file loading and avoid false positives during static analysis.
- **Type checker compatibility**: `config.py` suppresses `ty: ignore[missing-argument]` on `Settings()` because `ty` does not understand `pydantic-settings` env-file defaulting. This follows root `AGENTS.md` Invariant #5 (Type Safety): suppression is allowed for third-party compatibility issues when scoped to the smallest region and annotated with the reason.
- **Correlation IDs**: Use `logging.py` utilities to propagate correlation IDs across async boundaries.
- **Model construction**: New code imports `create_model_client()` from `@app/model_gateway/factory.py`
  and selects a configured route alias. Provider SDK clients exist only inside model-gateway adapters.
- **Authorization context**: Protected APIs must depend on `get_active_auth_context`, `get_active_user_id`, `get_admin_user_id`, `require_roles`, or `require_scopes` so Redis token revocation is enforced. Signature-only helpers are for token parsing and compatibility tests, not route protection.
- **Browser transport**: Cookie-authenticated unsafe requests require canonical CSRF and Origin checks; Bearer-only requests remain CSRF-independent, and ambiguous credentials fail closed.
- **Tenant binding**: Production request and worker paths bind a resolver-produced `TenantContext`. `set_current_tenant_id()` and the configured `default` tenant are limited to explicit local/test/bootstrap work.
- **Database tenant binding**: SQLAlchemy centrally applies `SET LOCAL` semantics through `set_config(..., true)` for `app.current_tenant_id`; never hand-set tenant GUCs in services or repositories.
- **RLS transaction lifecycle**: Initial tenant binding occurs at `after_begin` and is valid only for
  that transaction. Context refresh may rebind an already-active transaction after trusted tenant
  resolution, but must not eagerly provision a new connection before the transaction begins.
- **Database capabilities**: Alembic/role provisioning uses `MIGRATION_DATABASE_URL`; API and tenant workers use the runtime login/capability, while outbox and scheduled maintenance use the separately deployed maintenance login/capability. Application RBAC never selects a database capability.
- **Storage namespaces**: Construct tenant Redis keys with `TenantNamespace`/`namespaced_key()`, system keys with `namespaced_system_key()`, and local object paths with `tenant_storage_path()`. Qdrant payloads and filters use the retrieval tenant-boundary seam; never hand-compose shared-storage namespaces.
- **Secret management**: Never log secrets or tokens; use `SecretStr` in Pydantic models.
- **Cache observability**: Cache and Redis diagnostics use operation/cache names and normalized
  error types only; never log Redis keys, values, query bodies, or payloads.
- **Database observability**: SQLAlchemy telemetry records only bounded engine role, SQL verb,
  pool-in-use count, and normalized error category. Never log or label statement text, bind values,
  tenant identities, or query payloads.
- **LLM caching**: Cache LLM instances in `llm_factory.py` to avoid repeated initialization.

## Anti-Patterns

- **Direct env access**: Never read `os.environ` outside `config.py`.
- **Hardcoded secrets**: Never hardcode API keys, passwords, or tokens.
- **RLS escape hatches**: Normal runtime code must not disable `row_security`, use `BYPASSRLS`, connect as a superuser/table owner, or expose the maintenance capability to request RBAC.
- **Synchronous I/O**: All core I/O must be async.

## Related Files

- `AGENTS.md` (root) — Defines repo-wide invariants that core modules enforce.
- `@app/api/v1/auth.py` — Uses `security.py` for authentication.
- `@app/celery_app.py` — Uses `config.py` for Celery configuration.
