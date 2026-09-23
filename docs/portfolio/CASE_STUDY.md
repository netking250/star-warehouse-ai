# Enterprise-Hardening Case Study

## Problem and goal

Star Warehouse AI began as a feature-rich FastAPI/LangGraph customer-service application. The
hardening program kept the useful modular-monolith shape while making identity, tenant isolation,
async delivery, model access, browser security, operations, and releases explicit and testable.
The progression ran from the initial AI customer-service system through enterprise
architecture hardening, tenant/security boundaries, reliable async and tool
execution, real RAG/model UAT, V1.1 UI redesign, reproducible V1.2 bootstrap,
and trusted CI artifact delivery. The result is an evidence-backed reference
implementation, not a production-scale claim.

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

- Accepted main `f852a8f2ce0f82fa6157d8bd72b0d1a1f8a1da40` passed all five
  protected CI families. Backend collected 1,957 tests: 1,920 passed, zero
  failed/errors, 37 skipped, and 81.85% coverage. Its single Alembic head is
  `f0a1b2c3d4e5`.
- T17 correlated one trace across API, outbox, and worker; delivered 27 metric families, three
  dashboards, and 11 alert rules.
- Trusted main published the immutable GHCR image at
  `sha256:fcdf1953843618d23509f32aa5c0e805e97fd5439d5fc384989cbf4fff9429d1`.
  Its OCI revision matches main, CycloneDX JSON 1.6 contains 255 components,
  trusted SLSA provenance names the same image digest, and Python/JavaScript
  CodeQL succeeded. The current blocking image policy recorded zero CRITICAL,
  81 HIGH, and 37 HIGH with known fixes; frontend dependencies recorded 9 HIGH.
- T19 exercised install/upgrade/rollback on a disposable k3s target with its 38-resource chart
  revision. T21's final chart render validated 42 resources statically. Neither stage proved a
  public VM, DNS, CA, or live AWS deployment.
- T20 request-load runs completed 537, 547, and 527 requests, averaging 14.46 requests/second with
  mean p50/p95/p99 of 112.39/412.85/604.75 ms. A two-minute run completed 1,707 requests with no
  request failures. Independent disposable restore evidence measured about 665 seconds RTO; RPO is
  the latest completed logical backup, not zero and not PITR.
- T21 adds 12 provider-free deterministic workflow scenarios. They measure routing, tool selection,
  approval, authorization, tenant separation, model failure policy, and terminal-state contracts;
  they do not measure real-model linguistic quality.
- P-UAT-03 passed 30/30 cases on a frozen synthetic real-provider Bailian
  corpus, with 4.10/5 average usability and zero measured tenant, approval,
  disclosure, or material no-answer hard-gate violations. UI V1.1 was accepted
  with Light/Dark, responsive Customer/Admin flows and accessibility corrections.
  Main passed 63/63 frontend unit tests; hosted Playwright succeeded with 13
  normal passes and one retry after transient browser-console 502 responses.
- V1.2's disposable fresh bootstrap, second idempotent run, and application
  restart verified persisted synthetic business data, Qdrant indexing,
  authentication, RLS, and async delivery. Main's Docker smoke proved build,
  migration, roles, API, and health; it did not run full business-data bootstrap.
  The final Helm render validated 42 resources.

## Trade-offs and limits

The modular monolith avoids premature distributed-service ownership while allowing runtime roles
to scale independently. At-least-once delivery requires idempotency. RLS is defense in depth, not a
substitute for application tenant filters. Mock evaluation is reproducible; the 30/30
real-provider result is bounded to its frozen synthetic corpus. Logical backup/restore
is narrower than PITR.

The complete and current limitations list is maintained in
[Known Limitations](../engineering/KNOWN_LIMITATIONS.md). In particular, this work does not claim
production HA or capacity, a long soak, live AWS, production object-store recovery,
public DNS/CA proof, PITR, or zero vulnerabilities. See the
[final acceptance baseline](../engineering/FINAL_ACCEPTANCE.md) for exact
trusted artifact identifiers and claim boundaries.
