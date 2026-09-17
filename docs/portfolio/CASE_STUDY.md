# Enterprise-Hardening Case Study

## Problem and goal

Star Warehouse AI began as a feature-rich FastAPI/LangGraph customer-service application. The
hardening program kept the useful modular-monolith shape while making identity, tenant isolation,
async delivery, model access, browser security, operations, and releases explicit and testable.
The goal was evidence-backed engineering readiness, not a microservice rewrite or a production
scale claim.

## Resulting design

- FastAPI serves the API and secure browser session. PostgreSQL is authoritative and applies RLS;
  Redis holds cache/checkpoint state, Qdrant provides retrieval, and tenant namespaces cross every
  store.
- Transactional Outbox commits business intent with database state. A separate relay publishes to
  RabbitMQ; Celery workers consume at-least-once messages with task context and idempotent receipts.
- The conversation runtime owns turn/run idempotency, cancellation, ordered events, recovery, and
  one terminal outcome. The Model Gateway normalizes provider contracts; the separate failure
  policy bounds retry, fallback, circuit breaking, and safe degradation.
- OpenTelemetry correlation crosses API, outbox, and worker boundaries. GitHub Actions retains five
  attributable protected check families and isolates trusted image publication from untrusted PRs.
- A digest-pinned Helm chart deploys API/worker/scheduler/outbox roles. A migration Job is the sole
  Kubernetes migration owner. The k3s flow is a disposable demo, while AWS remains a qualified
  reference rather than a live deployment claim.

## Evidence

- T14 full regression collected 1,819 tests: 1,780 passed, 2 known timing-sensitive baseline tests
  failed, 37 skipped, and coverage was 81.62% in 1,776.35 seconds.
- T17 correlated one trace across API, outbox, and worker; delivered 27 metric families, three
  dashboards, and 11 alert rules.
- T18 recorded a 255-component SBOM, zero Gitleaks findings, npm findings of 0 critical / 9 high /
  4 moderate / 1 low, pip-audit findings of 83 across 19 packages, and Trivy findings of 0 critical /
  81 high with 37 fixable.
- T19 exercised install/upgrade/rollback on a disposable k3s target with its 38-resource chart
  revision. T21's final chart render validated 42 resources statically. Neither stage proved a
  public VM, DNS, CA, or hosted GHCR publication.
- T20 request-load runs completed 537, 547, and 527 requests, averaging 14.46 requests/second with
  mean p50/p95/p99 of 112.39/412.85/604.75 ms. A two-minute run completed 1,707 requests with no
  request failures. Independent disposable restore evidence measured about 665 seconds RTO; RPO is
  the latest completed logical backup, not zero and not PITR.
- T21 adds 12 provider-free deterministic workflow scenarios. They measure routing, tool selection,
  approval, authorization, tenant separation, model failure policy, and terminal-state contracts;
  they do not measure real-model linguistic quality.
- T21's final local gates passed locked frontend validation (12 Vitest files/51 tests and 6/6 browser
  tests), a detached clean-checkout Docker build/startup/health smoke, Helm lint/template/schema/
  kubeconform/ShellCheck, and route/security/CI static checks. The full backend result was 1,848
  collected, 1,810 passed, one historical nondeterministic chat timeout failure, zero errors, 37
  skipped, and 81.93% coverage; no T21 feature regression was demonstrated.

## Trade-offs and limits

The modular monolith avoids premature distributed-service ownership while allowing runtime roles
to scale independently. At-least-once delivery requires idempotency. RLS is defense in depth, not a
substitute for application tenant filters. Mock evaluation is reproducible but cannot establish
live-provider answer quality. Logical backup/restore is intentionally narrower than PITR.

The complete and current limitations list is maintained in
[Known Limitations](../engineering/KNOWN_LIMITATIONS.md). In particular, this work does not claim
production HA or capacity, a long soak, live AWS, object-store recovery, hosted attestation/GHCR
proof, public DNS/CA proof, PITR, or zero vulnerabilities.
