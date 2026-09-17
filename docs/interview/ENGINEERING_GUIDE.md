# Engineering Interview Guide

Use this guide to explain work implemented and tested in this repository. It is not a substitute
for production operating experience.

## Modular monolith and async delivery

**Problem.** API latency, background work, and schema ownership needed clear boundaries without a
broad service rewrite. **Design.** One codebase exposes independently runnable API, worker,
scheduler, and outbox-relay roles. PostgreSQL and a transactional outbox bridge committed business
state to RabbitMQ/Celery. Redis is cache/checkpoint/result infrastructure, not the broker.
**Trade-off.** This keeps ownership and local development simpler, but roles remain coupled to one
release. At-least-once delivery requires idempotent receipts. **Failure mode.** A publish failure
leaves a leased/retryable outbox row instead of losing committed intent. **Evidence.** T08/T09 tests
cover envelope validation, concurrent claims, retry, receipt deduplication, and dependency recovery.

## Tenant isolation and browser trust

**Problem.** Application filters alone are too fragile for tenant and browser boundaries.
**Design.** The resolver supplies a non-default production `TenantContext`; PostgreSQL binds it
transaction-locally and enforces RLS, while other stores use tenant namespaces. The browser uses an
HttpOnly session cookie, in-memory CSRF, exact trusted origins, and credential-free WebSocket URLs.
**Trade-off.** Every request/task must explicitly bind context and state-changing calls carry CSRF.
**Failure mode.** Missing tenant context and stale authorization fail closed; logout/revocation
invalidates current state. **Evidence.** T07/T10/T15/T16 isolation, route-inventory, cookie, CSRF,
origin, 401/403, and protected-route tests; T21 adds deterministic denial and namespace scenarios.

## Conversation runtime and streaming cancellation

**Problem.** Retries and disconnects can duplicate turns or terminal events. **Design.** PostgreSQL
owns turn/run lifecycle and idempotency keys; ordered events and explicit state transitions enforce
one terminal outcome. Cancellation propagates through the executor/stream boundary.
**Trade-off.** State transitions are stricter and recovery is database-led. **Failure mode.** A
duplicate request reuses its authoritative record; a cancelled/completed run rejects conflicting
terminal transitions. **Evidence.** T12 lifecycle/recovery tests and T21 cancellation, invalid
transition, and terminal-uniqueness scenarios.

## Model Gateway versus failure policy

**Problem.** Provider SDK differences and transient failure behavior are separate concerns.
**Design.** The T13 gateway defines provider-neutral capabilities, requests, responses, and stream
events. T14 wraps routes with bounded retry budgets, circuit state, ordered fallback, and only
explicit safe degradation. **Trade-off.** Configuration is more explicit, but providers cannot hide
fallback behavior internally. **Failure mode.** Retriable failure may move to the next candidate;
unsafe failure returns a structured error rather than fabricated content. **Evidence.** T13/T14
tests and T21 deterministic retry/fallback/degradation scenarios. Mock results do not measure live
model prose quality.

## Observability across async boundaries

**Problem.** A request can cross API, database outbox, RabbitMQ, and worker execution.
**Design.** Trace and correlation metadata travels in the task envelope; metrics and structured logs
share stable low-cardinality fields. **Trade-off.** Async spans may be linked rather than one
continuous process-local stack. **Failure mode.** Operators correlate a failed publish/consume path
by trace, task, tenant-safe metadata, queue, and receipt state. **Evidence.** T17 demonstrated a
shared API/outbox/worker trace, 27 metric families, three dashboards, and 11 rules.

## CI, migrations, deployment, and recovery

**Problem.** Untrusted code must not gain publish credentials, and replicas must not race schema
updates. **Design.** Five attributable PR check families run with read-only defaults. Trusted
main/version-tag runs own image publication, SBOM, and provenance. Helm uses immutable digests and
a single pre-install/pre-upgrade migration Job; applications never migrate at startup.
**Trade-off.** Hosted publication evidence arrives only after the final accepted PR/main flow.
**Failure mode.** PRs cannot publish; failed migration blocks rollout; backup restore targets must be
explicitly disposable. **Evidence.** T18 workflow review/scans, T19 38-resource k3s validation, and
T20 independent logical restore around 665 seconds.

## Reading the numbers honestly

T20's 14.46 requests/second average and mean 112.39/412.85/604.75 ms p50/p95/p99 describe only the
bounded disposable profile. The 1,707-request two-minute run is not a long soak. Restore RTO is the
measured procedure time; RPO is the latest completed logical backup. Neither result establishes
production capacity, HA, zero RPO, or PITR. See the
[evidence index](../portfolio/EVIDENCE_INDEX.md) and
[known limitations](../engineering/KNOWN_LIMITATIONS.md) before making broader claims.
