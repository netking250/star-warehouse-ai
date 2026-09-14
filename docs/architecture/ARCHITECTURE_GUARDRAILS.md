# Architecture Guardrails

This document is the single source of truth for structural changes during T02–T21. It turns the accepted enterprise-hardening decisions into short review rules. If this document conflicts with an accepted ADR, the ADR wins and this document must be updated in the same change.

## Baseline and Scope

- The application remains a **modular monolith**. API, Worker, Scheduler/Beat, and Outbox Relay are allowed independent deployment boundaries; they are not authorization for a broad microservice split.
- `conversation`, `task_runtime`, `tenancy`, `identity`, `authorization`, `compliance`, `model_gateway`, `memory`, `observability`, and `operations` are planned responsibility boundaries. Create a module, service, or interface only when its owning task delivers a real seam and callers.
- Guardrails apply immediately to new and changed code. Confirmed legacy exceptions are `CURRENT_DEBT`; they may remain until their mapped task, but must not spread.
- Structural changes update the nearest `AGENTS.md` only when local guidance actually changes. Do not copy this document into scoped instruction files.

## Dependency Direction

Runtime call flow may be read as:

```text
API / Transport
      ↓
Application / Runtime
      ↓
Domain Policy / Ports
      ↓
Infrastructure Adapters
```

Source dependencies point inward: transport depends on application entry points; application depends on domain policy and Port contracts; infrastructure implements Ports and is connected at the composition root. Domain/business policy must not import FastAPI routes, Celery tasks, LangGraph internals, or concrete provider SDKs. Infrastructure must not become the owner of business policy merely because it executes the I/O.

Current package names are transitional, not a mandate to move files in T01:

| Responsibility | Current placement and rule |
| --- | --- |
| Transport | `app/api`, `app/websocket`, and Celery task entry points map protocols to typed application calls. |
| Application/runtime | `app/services`, `app/graph`, `app/agents`, and `app/tools` currently share orchestration responsibilities; later tasks create seams incrementally. |
| Domain/Ports | Business policy and stable contracts must remain framework- and provider-independent. `app/adapters/ports.py` is an existing Port seam. |
| Infrastructure | `app/core`, concrete adapter implementations, persistence, queues, vector stores, and providers implement I/O behind stable contracts. |
| Composition | Startup/bootstrap code selects implementations; callers do not select provider SDKs inline. |

## Guardrails

### G1 — No Big Bang Rewrite

Refactor in the sequence `new seam → migrate callers → verify → retire old responsibility`. Preserve working paths through tested compatibility layers. Do not rewrite the system or split it into microservices to appear enterprise-grade.

### G2 — Business Logic Out of API Routes

Routes own transport, request/response validation, authentication context, authorization invocation, and response mapping. They must not accumulate business workflow, transaction orchestration, Celery delivery logic, or model-provider logic. Existing route debt is migrated under its mapped task, not expanded.

### G3 — LangGraph Is an Implementation Detail

The future `ConversationRuntime` exposes a stable typed interface. Callers must not depend on graph node names, raw graph-state keys, or internal transitions. T12 owns that seam; T01 does not implement it.

### G4 — Explicit Async Boundary

Do not add direct `some_task.delay(...)` or equivalent broker publication as the reliability boundary for a critical business side effect. T03-migrated business code persists a sanitized TaskEnvelope through the transactional outbox; classified best-effort/system calls may still use the task-runtime direct-dispatch seam. T04 owns broker migration and consumer idempotency.

### G5 — Tenant Context Is Mandatory

Persistence, cache, vector, asynchronous, and object-storage operations require an explicit trusted tenant boundary. An implicit default tenant is never production behavior. Missing, invalid, or conflicting tenant context fails closed at the boundary.

### G6 — Authentication Is Not Authorization or Tenancy

Keep responsibilities distinct: Authentication answers **who are you**; Authorization answers **what may you do**; TenantContext answers **on whose behalf and for which tenant**. A valid identity alone neither grants permission nor selects a tenant.

### G7 — Providers Are Adapters

Business and application policy must not bind to the OpenAI SDK, DashScope SDK, Qdrant client details, or an external ERP SDK. Stable Ports own the contracts; provider-specific configuration, errors, retries, and DTO translation stay in infrastructure adapters.

### G8 — Transaction Ownership Must Be Clear

Each business use case declares one transaction owner. Nested collaborators do not independently commit. A sequence such as `service A commits → service B commits → task publishes` must not be described as atomic. Durable follow-up work joins the business transaction through the outbox once T03 supplies it.

### G9 — No Fail-open for Critical Trust Decisions

Infrastructure failure during security, authorization, PII, high-risk action, grounding, or safety decisions must never silently become `ALLOW`, `SAFE`, or `VERIFIED`. The boundary explicitly selects and tests one outcome: fail closed, degraded operation with restricted capability, or manual review.

### G10 — Enterprise Claim Requires Evidence

Claims such as high availability, GDPR, auto-healing, production-ready, zero-downtime, multi-tenant isolation, or reliable delivery require all three: implementation, a relevant test, and recorded evidence. Without all three, README and documentation label the capability `target`, `reference architecture`, `planned`, or `partial`. Demo evidence must not be presented as production evidence, and engineering controls must not be presented as certification.

### G11 — Migration Immutability

T00's explicitly authorized pre-production migration-chain repair is complete. From T01 onward, an Alembic revision that reached a shared environment or is marked released/applied is immutable by default. Schema changes add a new revision and use `Expand → Backfill → Switch → Contract` for complex evolution. Editing historical migration code requires an append-only ADR with a concrete compatibility reason and rollout evidence. The revision graph must have exactly one head.

### G12 — Tests Across Real Seams

Critical enterprise capabilities cannot be proven only by mocked internals. Their owning tasks progressively add evidence for fresh-database migration, cross-session persistence, RLS isolation, duplicate delivery, outbox recovery, provider fallback, RBAC, PII persistence regression, and restore verification. Unit mocks remain appropriate for narrow failure paths but are not end-to-end evidence.

## Architecture Debt Register

The register is intentionally limited to confirmed, roadmap-relevant debt. `CURRENT_DEBT` is not a waiver for new code.

| Confirmed current debt | Status | Target task |
| --- | --- | --- |
| Request-local context and Celery payloads lacked a trusted async tenant/task envelope. Request-sourced paths are implemented, verified, and externally accepted. | `RESOLVED_T02` | T02 |
| Direct post-commit Celery publication can lose critical side effects. Refund/order and knowledge-sync critical paths now use the transactional outbox; external acceptance is pending. | `T03_AWAITING_ACCEPTANCE` | T03 |
| Celery delivery, retry, duplicate handling, and broker boundaries are not yet the target reliable runtime. | `CURRENT_DEBT` | T04 |
| PostgreSQL/Qdrant memory writes lack a demonstrated recoverable consistency seam. | `CURRENT_DEBT` | T05 |
| Tenant enforcement and database RLS need complete cross-storage and database evidence. T06 and T07 are externally accepted after forced RLS, transaction-local context, runtime-role, and full-regression evidence. | `RESOLVED_T07` | T07 |
| Enterprise identity now has a distinct generic OIDC and durable binding seam; authorization policy overlap remains explicitly owned by T09. | `T08_VERIFY_PENDING` | T08/T09 |
| Browser authentication still requires the frozen secure session boundary. | `CURRENT_DEBT` | T10 |
| PII lifecycle, retention/export/erasure, and evidence-backed compliance controls are incomplete. | `CURRENT_DEBT` | T11 |
| `chat.py`, graph internals, raw state, direct side effects, and oversized graph nodes leak orchestration responsibility. | `CURRENT_DEBT` | T12 |
| Model/provider construction and concrete provider behavior are not yet governed through one gateway and failure policy. | `CURRENT_DEBT` | T13/T14 |
| Frontend streaming/session transport still needs the target boundary and failure behavior. | `CURRENT_DEBT` | T15 |
| Enterprise controls, observability, and README-visible claims need evidence-backed visibility and qualification. | `CURRENT_DEBT` | T16/T17 |

Transaction-boundary cleanup travels with the owning seams, principally T03 and T12. Older architecture documents that describe Redis as the target Celery broker or otherwise present current implementation as the frozen enterprise target are documentation drift; ADR-009 and this document remain authoritative until the mapped task updates them.

## Review Checklist

Before accepting a structural change, confirm that it follows the dependency rule, does not add a direct critical `.delay(...)` call, carries explicit tenant context at new I/O boundaries, names the transaction owner, keeps provider details behind a Port, chooses a non-fail-open trust outcome, preserves migration immutability, and qualifies every enterprise claim with evidence.
