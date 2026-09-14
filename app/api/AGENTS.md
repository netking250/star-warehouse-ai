# AGENTS.md - API

> **IMPORTANT**: Read the root [`AGENTS.md`](../../AGENTS.md) first for repo-wide rules.

## Maintenance Contract

- This file is a living document for the API layer.
- Update this file in the same PR when adding new routes, endpoints, or changing API conventions.

## Read Order

1. Read the root [`AGENTS.md`](../../AGENTS.md) for repo-wide rules, commands, and routing.
2. Read this file for API-specific guidance.

## Overview

FastAPI router layer defining RESTful and WebSocket endpoints for the agent system. Organized under `@app/api/v1/` with admin subroutes.

Note: WebSocket routes (`@app/api/v1/websocket.py`) are the FastAPI entrypoints that delegate connection management to `@app/websocket/manager.py`.

## Key Files

| Role | File | Notes |
|------|------|-------|
| Chat API | `@app/api/v1/chat.py` | POST /chat (SSE streaming, 60/min IP + 10/min per-user rate limits), POST /feedback |
| Auth API | `@app/api/v1/auth.py` | Bearer compatibility login/register, browser login/cookie/CSRF, OIDC callback, current-user, and logout endpoints |
| WebSocket API | `@app/api/v1/websocket.py` | WS /ws/{thread_id}, WS /ws/admin/{admin_id} |
| Status API | `@app/api/v1/status.py` | Thread status endpoints |
| API schemas | `@app/api/v1/schemas.py` | Pydantic request/response schemas (legacy location) |
| Chat utilities | `@app/api/v1/chat_utils.py` | SSE metadata message utilities (v4.1 confidence metadata) |
| Admin agent config | `@app/api/v1/admin/agent_config.py` | Agent configuration admin endpoints |
| Admin complaints | `@app/api/v1/admin/complaints.py` | Complaint management endpoints |
| Admin analytics | `@app/api/v1/admin/analytics.py` | Analytics data endpoints |
| Admin feedback | `@app/api/v1/admin/feedback.py` | Feedback management endpoints |
| Admin experiments | `@app/api/v1/admin/experiments.py` | A/B experiment admin endpoints |
| Admin alerts | `@app/api/v1/admin/alerts.py` | Alert management admin endpoints |
| Admin evaluation dashboard | `@app/api/v1/admin/evaluation_dashboard.py` | Evaluation dashboard endpoints |
| Admin metrics | `@app/api/v1/admin/metrics_dashboard.py` | Metrics dashboard endpoints |
| Admin review queue | `@app/api/v1/admin/review_queue.py` | Human review queue admin endpoints |
| Admin token usage | `@app/api/v1/admin/token_usage.py` | Token usage and cost tracking admin endpoints |
| Admin authorization | `@app/api/v1/admin/authorization.py` | Tenant membership, effective authority, role assignment, and revocation endpoints |
| Admin compliance | `@app/api/v1/admin/compliance.py` | Approval decisions and bounded retention dry-run/execution endpoints |
| App entry | `@app/main.py` | FastAPI application entry point, router mounting, middleware, health endpoint |

## Commands

```bash
# Run API tests
uv run pytest tests/test_chat_api.py tests/test_auth_api.py tests/test_admin_api.py
uv run pytest tests/api/
```

## Code Style

General Python rules are defined in the root `AGENTS.md`. API-specific conventions:

- **Type hints**: All route handlers must have complete type annotations.
- **Async routes**: All FastAPI routes must be `async`.
- **Response models**: Use Pydantic response models for all endpoints.
- **Error handling**: Use FastAPI exception handlers; never return raw exceptions.

## Testing Patterns

- Test each endpoint with mocked services.
- Verify SSE streaming format in chat tests.
- Test auth middleware and permission checks.
- Mock WebSocket connections for websocket tests.

## Conventions

- **Versioning**: All routes under `/api/v1/` prefix.
- **SSE format**: Chat responses use SSE with `data:` prefix and JSON payload.
- **Auth transport**: Preserve OAuth2 Bearer tokens for non-browser clients and use the canonical
  HttpOnly application-token cookie for browsers; both must normalize through the same dependency
  and authorization context.
- **OIDC transport**: Routes start/finish the generic provider flow and map stable errors only; durable identity resolution and linking policy stay in `IdentityService`.
- **Browser session transport**: Browser login and OIDC completion set the canonical HttpOnly cookie; `/browser/csrf` exposes only session-bound CSRF state, and logout revokes before clearing the cookie.
- **Tenant context**: Protected business routes use `AuthorizationContext = Depends(get_authorized_auth_context)` (or the canonical user-ID adapter); reserve `get_active_auth_context` for explicitly `AUTHENTICATED` routes such as `/me` and `/logout`. Never accept `tenant_id` from an untrusted request body when it is already available in the authenticated principal.
- **Task dispatch**: Critical state-changing routes enqueue a sanitized envelope through `@app/outbox/` before their transaction commits. Classified best-effort or non-transactional work may use `@app/task_runtime/dispatch.py`. Never call Celery `.delay()` or `.apply_async()` in a route.
- **PII boundary**: Once chat input is filtered, background telemetry/evaluation/memory payloads receive only the sanitized text or smaller metadata.
- **Revocation**: Every protected REST/SSE/WebSocket entry point must check Redis-backed token revocation; do not use signature-only JWT helpers as route dependencies.
- **Authorization policy**: Protected routes enforce the exact capability declared in `@app/authorization/route_inventory.py`; adding a route without an explicit classification fails startup and structural tests.
- **Admin routes**: All admin routes under `/api/v1/admin/` use current local tenant role state rather than JWT or OIDC role claims.
- **Rate limiting**: Chat endpoint enforces dual rate limits: 60 req/min per IP (slowapi) and 10 req/min per user (Redis-based fixed window). Per-user limits are checked before LLM calls to prevent abuse.

## Anti-Patterns

- **Business logic in routes**: Keep routes thin; delegate to services.
- **Missing response models**: Always define response models for type safety.
- **Synchronous blocking**: Never use sync I/O in async route handlers.

## Related Files

- `@app/services/` — Business logic services consumed by API routes.
- `@app/schemas/` — Pydantic schemas for request/response validation.
- `@app/core/security.py` — JWT token creation and validation.
