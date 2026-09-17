# Enterprise Hardening Roadmap

This is the execution roadmap for the frozen enterprise-hardening target. It owns T-INIT through T21 status and task gates. The older [`docs/roadmap-star-warehouse-ai.md`](../roadmap-star-warehouse-ai.md) remains a product/history roadmap and is not a substitute for this ledger.

## Status vocabulary

Allowed task statuses are:

`NOT_STARTED`, `IN_PROGRESS`, `BLOCKED`, `NEEDS_EVIDENCE`, `AWAITING_ACCEPTANCE`, `PASS`, `PASS_WITH_NOTES`, `FAIL`.

Codex may set a completed implementation to `AWAITING_ACCEPTANCE` only. `PASS` and `PASS_WITH_NOTES` require an explicit external acceptance instruction.

## Task tree

| Task | Name | Status |
| --- | --- | --- |
| T-INIT | Persistent Project Memory | PASS |
| T00 | Reproducible Green Baseline | PASS |
| T01 | Architecture Guardrails | PASS |
| T02 | Trusted Request / Task Context | PASS |
| T03 | Transactional Outbox | PASS |
| T04 | RabbitMQ + Reliable Celery | PASS |
| T05 | Memory Consistency | PASS |
| T06 | Tenant Hardening | PASS |
| T07 | PostgreSQL RLS | PASS |
| T08 | Enterprise Identity | PASS |
| T09 | Authorization | PASS |
| T10 | Secure Browser Session | PASS |
| T11 | Compliance Lifecycle | PASS |
| T12 | Conversation Runtime | PASS |
| T13 | Model Gateway | PASS |
| T14 | AI Failure Policy | PASS_WITH_NOTES |
| T15 | Frontend Transport | PASS |
| T16 | Enterprise Console | PASS |
| T17 | Observability | PASS |
| T18 | CI/CD + Supply Chain | PASS_WITH_NOTES |
| T19 | Helm + k3s + AWS Reference | AWAITING_ACCEPTANCE |
| T20 | Performance + Failure + DR | NOT_STARTED |
| T21 | Eval + Portfolio + Interview | NOT_STARTED |

## Independent maintenance tasks

These tasks improve repository governance without advancing or bypassing the
T00–T21 gate sequence.

| Task | Name | Status |
| --- | --- | --- |
| M01 | Repository Consolidation & Legacy Cleanup | PASS |
| M02 | Git Main Consolidation & Branch Cleanup | PASS |

## T-INIT-FIX — Disaster Recovery Decision

- **Status:** T-INIT is externally accepted `PASS`.
- **Decision record:** [`ADR-020`](DECISIONS.md#adr-020--disaster-recovery-and-restore-verification) records the accepted Disaster Recovery baseline.
- **Scope:** Demo automated backups and Restore Test; Production Reference HA and PITR; explicit RPO/RTO; Restore Runbook; recovery verification evidence; profile-specific topology and cost tiers.
- **At fix completion:** T00 was `IN_PROGRESS`; consult the task tree for its current status.

## T14-T21 Solo Development Workflow

T14 through T21 use one long-lived integration branch:
`feat/t14-t21-enterprise-hardening`.

Each stage follows:

`IMPLEMENT → VERIFY → external acceptance → next stage`

- No PR is required per T-stage.
- No branch is created per T-stage.
- A mandatory human reviewer is not required.
- Each stage keeps logically separated commits.
- Work does not happen directly on `main`.
- No force push is used on `main`.
- One final PR is planned after T21.
- Automated CI gates remain mandatory for the final PR.

### Test strategy

- Normal `IMPLEMENT`: run targeted tests.
- Normal `VERIFY`: run targeted/regression tests appropriate to the changed subsystem.
- The full backend suite is not mandatory after every T-stage.
- Run the full backend suite when the current stage is cross-cutting/high risk, a blocker needs
  proof, at T21/final integration, or as part of final CI/PR.

### Failure triage

- A feature-only reproducible failure is a current-stage blocker.
- The same failure on protected `main` receives baseline-debt classification first.
- A non-reproducible transient failure is recorded; no fix is invented.
- An environment failure is fixed in the environment, not in business code.
- Historical debt is not infinitely cleaned during unrelated feature work.

### Deferred baseline test debt

`DEFERRED_BASELINE_TEST_DEBT` remains recorded for:

- OpenAI SDK cold-start deadline sensitivity.
- Celery fresh-process import deadline sensitivity.

Repair these only if final integration CI is blocked, they become materially worse, or explicit
test-hardening work is scheduled. They are not resolved by T14 and do not block T15.

## T15 Implementation Start

- Status: `IN_PROGRESS`.
- Execution stage: `IMPLEMENT`.
- Branch: `feat/t14-t21-enterprise-hardening`.
- T14 remains externally accepted `PASS_WITH_NOTES`; T16 is externally accepted `PASS` by explicit
  user instruction.
- The two deferred protected-main baseline debts remain unresolved and are not in T15 scope.
- T15 adds no backend route, database migration, or schema change.

## T15 Implementation Closeout

- Status: `IN_PROGRESS`.
- Execution stage: `VERIFY_PENDING`.
- The canonical HTTP client, SSE reader/run state machine, cookie/origin WebSocket client, auth
  state handling, normalized transport errors, CSRF, cancellation, bounded retry policy, and
  security guards are implemented on `feat/t14-t21-enterprise-hardening`.
- Frontend format check, lint, typecheck/build, full frontend unit tests (`10` files, `47` tests),
  and targeted Playwright session/login flows (`2` tests) passed. The focused T10 browser-session
  and WebSocket compatibility guards passed (`22` tests), focused OIDC token-free browser tests
  passed (`3`), and the route inventory guard passed.
- `uv run alembic heads` reports the one accepted head `e9f0a1b2c3d4`. No migration, schema, or
  backend application change was made. The full backend suite was intentionally not run.
- T14 remains `PASS_WITH_NOTES`; T16 remains `NOT_STARTED`; the two protected-main baseline
  deadline debts remain deferred and do not block T15.

## T15 Verification Closeout

- Status: `AWAITING_ACCEPTANCE`.
- Execution stage: `EXTERNAL_ACCEPTANCE_PENDING`.
- Final verification passed on `feat/t14-t21-enterprise-hardening` from implementation head
  `93fde48077a998619ddce3c6c67b26abcde71f72`; the synchronized remote and clean working tree
  were confirmed.
- Frontend format check, lint, TypeScript/build, Vitest (`10` files, `47` passed, `0` failed,
  `0` skipped), and focused Chromium E2E (`2` passed) are green.
- Focused T10 compatibility passed `26` tests; focused T12/T14 logical cancellation, terminal,
  and provider-fallback compatibility passed `7` tests. The route guard reports zero unclassified
  HTTP/WS routes, and `uv run alembic heads` reports the single head `e9f0a1b2c3d4`.
- No full backend regression was run. No application code, backend route, migration, schema, or
  T16 work changed during verification; no feature-hiding skip/xfail/todo was added.
- The OpenAI SDK cold-start and Celery fresh-process import deadline sensitivities remain
  `DEFERRED_BASELINE_TEST_DEBT` and do not block T15.

T14 remains `PASS_WITH_NOTES`; T15 and T16 are externally accepted `PASS` by explicit user
instruction. T17 is the active implementation stage.

## Gate rules

- T-INIT through T13 and M01-M02 are accepted `PASS`. T14 is externally accepted `PASS_WITH_NOTES`.
  The two deferred protected-main baseline test debts are recorded and do not block T15.
- A task in `AWAITING_ACCEPTANCE`, `FAIL`, `NEEDS_EVIDENCE`, or `BLOCKED` is not accepted as a prerequisite for the next task.
- Do not skip a task because an older roadmap claims similar work is complete. Use current code and current verification evidence.
- A task plan starts in `docs/exec-plans/active/Txx.md` and moves to `completed/` only after external acceptance.
- Historical execution records in [`EXECUTION_LOG.md`](EXECUTION_LOG.md) are append-only. Current state is always [`PROJECT_STATE.md`](PROJECT_STATE.md).

## Suggested dependency flow

`T-INIT → T00 → T01 → T02 → T03 → T04 → T05 → T06 → T07 → T08 → T09 → T10 → T11 → T12 → T13 → T14 → T15 → T16 → T17 → T18 → T19 → T20 → T21`

The sequence is the default gate order. A user may issue a documented change request, but any dependency exception must be recorded in `PROJECT_STATE.md` and the active plan before implementation.

## T19 Implementation Start

- Status: `IN_PROGRESS`.
- Execution stage: `IMPLEMENT`.
- Branch: `feat/t14-t21-enterprise-hardening`.
- T18 is externally accepted `PASS_WITH_NOTES` by the explicit T19 instruction. T20 and T21 remain
  `NOT_STARTED`.
- Frozen scope is ADR-015/ADR-016 plus the explicit T19 instruction: one understandable Helm chart,
  a low-cost k3s demo profile, an AWS EKS production reference, immutable trusted-image
  consumption, secret references, one release migration owner, TLS ingress, truthful probes and
  security defaults, and reproducible deployment validation.
- No application business-code change, migration, live AWS provisioning, production image
  publication, T20 performance/DR work, or T21 hosted-gate work is in scope. Hosted registry proof
  and real-VM k3s proof may be explicitly deferred when the local environment cannot provide them.
- The active plan is [`docs/exec-plans/active/T19.md`](../exec-plans/active/T19.md).

## T19 Implementation Closeout

- Status remains `IN_PROGRESS`; execution stage is `VERIFY_PENDING`. External verification and
  acceptance are still required.
- One canonical chart now models the existing modular-monolith process boundaries, a
  revision-scoped single migration owner, immutable digest-first images, Secret references, TLS
  ingress, non-root pods, baseline resources/probes, the low-cost k3s demo dependencies, and the
  production/AWS reference profile without creating AWS infrastructure.
- Disposable k3s `v1.35.5+k3s1` via k3d passed install, upgrade, rollback, migration idempotency,
  HTTPS health, workload readiness, and an explicit missing-Secret failure with atomic recovery.
  Helm lint/template, schema use, strict Kubernetes validation, script/workflow static checks,
  rendered security scan, the accepted Alembic head, and route inventory passed.
- Hosted registry/attestation evidence remains deferred to T21. A real public VM/DNS/CA run remains
  environment-specific VERIFY evidence. T20 performance, resilience, backup/restore, DR, and
  capacity work remains `NOT_STARTED`.

## T19 Verification Closeout

- Status: `AWAITING_ACCEPTANCE`.
- Execution stage: `EXTERNAL_ACCEPTANCE_PENDING`; Codex does not mark T19 `PASS`. T20 remains
  `NOT_STARTED`.
- Final verification used the synchronized `feat/t14-t21-enterprise-hardening` branch at
  `31536460a808cffa3847261d4db681a2086b9eb9` with a clean worktree. Independent Helm lint/template,
  strict kubeconform (`38` valid objects, `0` invalid/errors/skipped), ShellCheck deployment checks,
  immutable digest/`latest` negative cases, rendered production security, migration ownership, and
  route/Alembic checks passed.
- A fresh disposable k3d `5.9.0` cluster with actual k3s `v1.35.5+k3s1` passed canonical install,
  complete workload/dependency readiness, HTTPS ingress, 2-replica API upgrade, atomic migration
  and missing-Secret failures, rollback without downgrade, graceful Pod replacement, and singleton
  scheduler/relay checks. No production namespace/database/credential, cloud resource, or image
  publication was touched.
- Runtime security and browser contracts remained intact: effective app UID/GID `999`, non-root,
  no privilege escalation/privileged/host access, no app API token, Secure HttpOnly cookies, CSRF,
  exact Origin, no browser bearer/query token, valid WS cookie/origin upgrade, invalid WS Origin and
  query-token rejection, HTTPS OIDC callback, and small authenticated upload. Public `/metrics` was
  not routed. SSE completion was not claimed because no supported runtime Mock-provider fixture is
  wired into the chart and no real provider was called; production stream/body annotations passed.
- T17 Helm smoke passed the OTLP Collector/Tempo path, API JSON log, internal API metric, four-span
  API trace, worker JSON log, worker trace lookup, and zero disposable Secret-sentinel matches.
  Existing scheduled maintenance-task tenant-context errors in the reused T18 image are recorded as
  non-blocking `PRE_EXISTING_BASELINE`; no application logic was changed during VERIFY.
- AWS remains reference-only. Hosted GHCR runtime/attestation, public VM/DNS/CA, live AWS deployment,
  T20 capacity/performance/DR work, and existing OpenAI/Celery timing debt remain deferred.

## T16 Implementation Start

- Status: `IN_PROGRESS`.
- Execution stage: `VERIFY_PENDING`.
- Branch: `feat/t14-t21-enterprise-hardening`.
- T14 remains externally accepted `PASS_WITH_NOTES`; T15 is `PASS` by explicit user acceptance
  instruction; T17 remains `NOT_STARTED`.
- Frozen scope is the existing frontend extension for Overview, AI, Operations, Security, and
  Compliance over already accepted backend contracts. No backend route, schema migration, provider
  secret management, T17 observability work, or T18-T20 deployment/performance work is in scope.
- The active plan is [`docs/exec-plans/active/T16.md`](../exec-plans/active/T16.md).

## T16 Implementation Closeout

- T16 remains `IN_PROGRESS` and is ready for external VERIFY; it is not marked PASS by Codex.
- The single enterprise console hierarchy now covers capability-aware Overview, Operations, AI,
  Security, and Compliance surfaces while preserving the stable existing workspaces.
- Frontend verification passed: format check, lint, TypeScript/build, Vitest `51 passed`, focused
  T15 transport guards `31 passed`, and Chromium E2E `6 passed`.
- Focused backend evidence passed against the disposable `test_t16_evidence_20260915` database on
  the repository's Compose PostgreSQL/Redis services: authorization `8` tests, compliance `5`
  tests, and implemented operations/runtime/AI reads `4` tests. The default host ports were
  occupied by unrelated containers, so loopback-only evidence ports were used without changing
  repository configuration.
- The direct application route inventory reported `0` unclassified HTTP/WS routes. Alembic remains
  at the single expected head `e9f0a1b2c3d4`; no migration or application code was added.
- No backend route, schema, migration, provider-secret management, T17 observability work, PR, or
  merge was added.

## T16 Verification Closeout

- T16 moves from `IN_PROGRESS / VERIFY_PENDING` to `AWAITING_ACCEPTANCE /
  EXTERNAL_ACCEPTANCE_PENDING`; Codex does not mark the task `PASS`.
- Focused Chromium acceptance passed `5` tests covering authorized navigation, capability denial,
  backend 403, compliance approval mutation, CSRF/state refresh, and login/logout.
- T16-targeted frontend tests passed `23` tests across `5` files. Format, lint, explicit TypeScript
  check, and production build passed; the complete 51-test frontend suite was not rerun.
- Compact backend smoke passed `8` tests covering authorization allow/deny, compliance approval and
  access-loss behavior, conversation metadata, dashboard summary, and AI configuration reads.
- Structural review confirmed canonical T15 transport, capability-aware navigation, scoped cache
  clearing/invalidation, safe error states, no secret/token rendering, and no unsupported audit,
  job/outbox, provider, circuit, tenant-switch, or T17-T20 controls.
- Route inventory remains at zero unclassified HTTP/WS routes. Alembic remains at the single head
  `e9f0a1b2c3d4`; no migration or historical migration modification was added.

## T17 Implementation Start

- Status: `IN_PROGRESS`.
- Execution stage: `VERIFY_PENDING`.
- Branch: `feat/t14-t21-enterprise-hardening`.
- T14 remains `PASS_WITH_NOTES`; T15 and T16 are `PASS` by explicit user instruction; T18-T20
  remain `NOT_STARTED`.
- The repository has no narrower T17 plan. The active scope is the explicit production
  observability hardening instruction: safe structured logs, bounded application metrics,
  W3C/OTel request and async correlation, worker/outbox/conversation/model signals, validated
  local observability provisioning, useful dashboards/alerts/runbooks, and focused evidence.
- No T02/T03/T04 context or delivery redesign, T16 UI expansion, database migration, public
  business route, CI/CD/SBOM/signing, deployment architecture, load/DR work, or baseline timing
  debt repair is in scope.
- The active plan is [`docs/exec-plans/active/T17.md`](../exec-plans/active/T17.md).

## T17 Implementation Closeout

- T17 remains `IN_PROGRESS / VERIFY_PENDING`; Codex does not mark the task `PASS`.
- The accepted observability stack was reused across API, worker, scheduler, outbox, conversation,
  model-policy, and database paths. Bounded metrics (including aggregate database query/pool/error
  signals), sanitized structured logs, W3C/TaskEnvelope tracing, dashboards, alerts, runbooks, and
  focused tests/config validation are implemented.
- Local stack readiness passed for Prometheus, Mimir, Grafana, Loki, Tempo, Alertmanager, and the
  OTel Collector. A deterministic synthetic failure was visible in Loki and Tempo with correlated
  safe identifiers. No route, migration, frontend change, T18/T19/T20 work, or baseline timing-debt
  repair was added.
- Focused verification and static checks passed. Existing DB/client fixture failures were isolated
  as test-infrastructure limitations; full backend regression remains intentionally out of scope.

## T17 Verification Attempt

- Attempted on 2026-09-16 with the canonical API, worker, scheduler, outbox relay, and disposable
  dependency runtime. Monitoring services remained ready and temporary verification resources were
  removed after the run.
- The canonical API was scraped successfully and emitted the normalized `/api/v1/login` HTTP metric
  with bounded labels. Its container had the active Collector endpoint configured.
- A real request with valid W3C `traceparent` and correlation metadata returned without `X-Trace-ID`;
  Tempo indexed scheduler traces but no `star-warehouse-ai-api` trace. This fails the real HTTP
  trace-correlation gate.
- Classification: `TRACE_PROPAGATION_FAILURE`. T17 remains `IN_PROGRESS / VERIFY_PENDING`; no code
  correction was made during VERIFY, and external acceptance is not ready.

## T17 API Trace Fix

- Status remains `IN_PROGRESS`; execution stage remains `VERIFY_PENDING`.
- Reproduced the missing API trace for five of five sampled requests while the scheduler control
  continued exporting through the same Collector. The first broken edge was FastAPI instrumentation:
  lifespan installed it after Starlette cached the ASGI middleware stack.
- Moved the existing API telemetry bootstrap before the first ASGI call and attached the existing
  correlation filter to the shared structured-log handler. No second provider, tracing abstraction,
  response header, Collector path, public route, migration, or trusted-context change was added.
- Post-fix real-stack proof passed `5/5` API traces in Tempo under `star-warehouse-ai-api`. One
  synthetic request correlated a normalized HTTP metric, Loki JSON record, and Tempo trace by the
  existing correlation/trace fields; scheduler traces remained available.
- Focused tests passed `17`; Ruff, format, ty, route inventory (`0` unclassified), Compose overlay
  validation, and Alembic head `e9f0a1b2c3d4` passed. T17 is ready to resume VERIFY, not acceptance.

## T17 Verification Evidence Closeout

- Status: `AWAITING_ACCEPTANCE`.
- Execution stage: `EXTERNAL_ACCEPTANCE_PENDING`.
- Disposable evidence used only the isolated `star-warehouse-ai-t17evidence` Compose project and
  existing test factories. The authorized tenant, principal, order/refund approval, PostgreSQL
  rows, Redis data, RabbitMQ test vhost, containers, network, and volumes were cleaned up; the
  long-lived developer databases and monitoring stack were not mutated.
- The accepted API -> transactional outbox -> relay -> RabbitMQ -> Celery workflow completed with
  two published outbox events, two successful task receipts, and one shared API/outbox/worker
  parent-child trace. ACK, retry, and idempotency semantics remained unchanged. Fixed HTTP smoke,
  deterministic failure correlation, T13/T14 logical-versus-attempt/fallback evidence, circuit
  state signals, and one-terminal T12 runtime evidence passed.
- The optional Tempo outage probe passed without business failure; Collector retry/queue behavior
  remained bounded and telemetry resumed after restoration. Runtime metric/Loki cardinality and
  redaction reviews found no sensitive identifiers, raw URLs, exception messages, prompts, or
  sentinel secrets. Grafana dashboards, eleven runtime-loaded rules, local Alertmanager routing,
  and representative real-metric queries passed. Mimir returned healthy NoData for T17 families
  because the canonical scrape target is a separate existing host-port service; isolated API
  registry/source evidence remained valid.
- The compact semantic matrix passed `29/29`; Ruff, format, ty, Compose, Prometheus/rules,
  Alertmanager, OTel, route inventory, and Alembic checks passed. No migration, route, frontend,
  T18-T20 work, or deferred OpenAI/Celery timing-debt repair was added.

State transition:

- T14 remains `PASS_WITH_NOTES`.
- T15 and T16 remain `PASS` by explicit user instruction.
- T17 moves from `IN_PROGRESS / VERIFY_PENDING` to `AWAITING_ACCEPTANCE /
  EXTERNAL_ACCEPTANCE_PENDING`; Codex does not mark it `PASS`.
- T18 remains `NOT_STARTED`.

## T18 Implementation Start

- Status: `IN_PROGRESS`.
- Execution stage: `IMPLEMENT`.
- Branch: `feat/t14-t21-enterprise-hardening`.
- T14 remains `PASS_WITH_NOTES`; T15, T16, and T17 are accepted `PASS` by the explicit T18
  implementation instruction. T19 and T20 remain `NOT_STARTED`.
- The repository contains no narrower T18 plan. The recovered frozen scope is ADR-016 plus the
  explicit T18 instruction: preserve the five existing CI gate families, harden workflow trust and
  lockfile determinism, add secret/dependency/image scanning, generate and validate a CycloneDX
  image SBOM, capture safe source metadata, and isolate trusted provenance from untrusted PRs.
- No branch-protection mutation, registry publication, image signing key, T19 deployment, T20
  performance/DR work, or deferred OpenAI/Celery timing-debt repair is in scope.
- The active plan is [`docs/exec-plans/active/T18.md`](../exec-plans/active/T18.md).

## T18 Implementation Closeout

- Status: `IN_PROGRESS`.
- Execution stage: `VERIFY_PENDING`.
- The five accepted CI gate families remain separate. Added read-only PR supply-chain analysis,
  frozen backend/frontend installs, explicit runtime versions, clean-checkout Docker smoke role
  provisioning, Gitleaks, locked dependency audits, archive-based Trivy/Syft scanning, CycloneDX
  SBOM, safe OCI/source metadata, PR Dependency Review, and trusted-context CodeQL/attestation
  configuration.
- Local evidence passed for actionlint, repository identity, backend quality, frontend gates,
  Docker build/non-root/metadata, disposable Compose migration/role/health smoke, current-checkout
  secret scan, SBOM parsing, and hardened image scanning. The hardened image has 0 critical Trivy
  findings; existing backend/frontend/high image findings are retained as visible warnings with
  reports and no suppressions.
- The hosted protected-PR run and trusted main/tag attestation proof are intentionally deferred to
  T21/final PR. No branch protection, PR, merge, registry publication, image signing, T19, T20, or
  deferred OpenAI/Celery timing-debt work was performed.

## T18 Verification Closeout

- Status: `AWAITING_ACCEPTANCE`.
- Execution stage: `EXTERNAL_ACCEPTANCE_PENDING`.
- Local verification reconfirmed a clean, synchronized `feat/t14-t21-enterprise-hardening` at
  implementation HEAD `940189b0d5db078d55c89147b27c2356a064bd89` before this documentation-only
  closeout. All workflow defaults remain `contents: read`; untrusted PR code cannot access trusted
  secrets, OIDC, attestation, package, release, or deployment writes. `pull_request_target` is
  absent, and the only job-level writes are narrowly scoped CodeQL security events and trusted
  main/tag attestation.
- Actionlint passed. Python 3.12, Node 22, uv 0.6.5, npm 11.9.0, frozen uv/npm installs, clean
  archive checks, lock mismatch failure fixtures, backend quality, frontend (`51` tests/build),
  Docker build/smoke evidence, Gitleaks sentinel/current-checkout checks, SBOM parsing, image
  metadata, and Trivy policy passed. Coverage remains `75%`; the full backend suite was not run.
- Current findings are explicitly retained: npm `0` critical / `9` high, pip-audit `83` records
  across `19` packages with no severity field, and Trivy `0` critical / `81` high / `37` high with
  known fixes. The active T18 plan records grouped IDs, runtime/dev scope, fix information,
  remediation recommendations, and dispositions. No broad lockfile update or suppression was
  added; no critical npm/image finding is present locally.
- Protected-PR execution and trusted hosted attestation are intentionally `NOT YET EXECUTED` and
  remain the T21 final-PR/main-or-tag gates. Main protection is unchanged, human reviewers remain
  `0`, and no PR, merge, registry publication, signing key, deployment, route, or migration work
  was performed. T19 and T20 remain `NOT_STARTED`.
