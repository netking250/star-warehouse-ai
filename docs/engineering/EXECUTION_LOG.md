# Execution Ledger

This file is append-only. It records what a task execution actually did and verified; it is not the current-state source of truth. Use [`PROJECT_STATE.md`](PROJECT_STATE.md) for current status.

## T-INIT — Persistent Project Memory

Started: 2026-09-11
Finished: 2026-09-11

Base Git HEAD: `bf0d5b9`

Objective:

Create the Git-tracked project execution memory system and root execution protocol required for cross-Codex context recovery.

Files Changed:

- `AGENTS.md` — added the managed Persistent Project Execution Protocol section.
- `docs/engineering/PROJECT_STATE.md` — added the current-state source of truth.
- `docs/engineering/ROADMAP.md` — added the T-INIT through T21 task tree and gate rules.
- `docs/engineering/DECISIONS.md` — recorded the frozen enterprise architecture baseline.
- `docs/engineering/EXECUTION_LOG.md` — added this append-only execution record.
- `docs/exec-plans/README.md` — documented task-plan lifecycle.
- `docs/exec-plans/active/T-INIT.md` — added the active T-INIT plan.
- `docs/exec-plans/completed/README.md` — documented the completed-plan area.

Commands Executed:

- `git status --short`
- `git branch --show-current`
- `git rev-parse --short HEAD`
- `rg --files -g 'AGENTS.md' -g 'AGENTS.override.md'`
- Repository structure, documentation, architecture, ADR, and CI/workflow inspection commands using PowerShell and `rg`.
- `git diff --check`
- Markdown target/path verification using PowerShell and `rg` for the new memory documents.
- `git status --short` after edits.

Verification:

- Root and nested AGENTS discovery completed; no `AGENTS.override.md` was found.
- No pre-existing `PROJECT_STATE`, execution ledger, or `docs/exec-plans` mechanism was found.
- Required new documents exist and link targets resolve to repository paths.
- T00–T21 are present in `ROADMAP.md` with T-INIT `AWAITING_ACCEPTANCE` and T00 `NOT_STARTED`.
- The new decision ledger contains the frozen architecture directions and states that accepted decisions are append-only.
- `git diff --check`: PASS.
- Full application, Docker, frontend, and E2E verification: NOT RUN; outside T-INIT scope.

Tests:

- No application tests were run because T-INIT changes are documentation-only and do not change application behavior.

Migration Changes:

- None.

Configuration Changes:

- None.

Known Issues:

- The four initiating P0 findings remain unverified and are explicitly carried into `PROJECT_STATE.md` for T00/T01 evidence.
- Existing product/architecture docs describe current or historical implementation details; this is recorded as potential documentation drift rather than silently corrected here.

Blockers:

- External acceptance is required before T00.

Task Result:

`AWAITING_ACCEPTANCE`

Next Recommended Task:

`T00 — Reproducible Green Baseline`

## T00 — Reproducible Green Baseline

Started: 2026-09-11
Finished: 2026-09-11

Base Git HEAD: `bf0d5b9`

Objective:

Establish a reproducible local engineering baseline using CI-representative commands, correct any narrow tooling defect found, and record unvarnished pass/fail/blocker evidence.

Files Changed:

- `app/core/limiter.py` — configured SlowAPI to use its tracked ASCII config file rather than reparse the UTF-8 root `.env` using the Windows default codec.
- `app/core/slowapi.env` — added the dedicated SlowAPI configuration file.
- `tests/core/test_limiter.py` — added the focused regression test for limiter initialization with the root `.env` present.
- `app/core/AGENTS.md` — documented the limiter configuration boundary.
- `docs/engineering/baselines/T00_BASELINE.md` — recorded actual baseline evidence.
- `docs/engineering/PROJECT_STATE.md`, `ROADMAP.md`, and this ledger — recorded T00 status and blockers.
- `docs/exec-plans/active/T00.md` — recorded verified findings and handoff.

Commands Executed:

- `uv sync --frozen`; backend Ruff, format, ty, pytest collection, focused regression, and formal CI pytest/coverage commands.
- `npm --prefix frontend ci`, format check, lint, test, and build.
- Alembic heads/history/current/upgrade checks, Docker version/Compose version/config checks, application import, and local dependency-port probes.
- `python scripts/check_project_identity.py` and final Git/state consistency checks.

Verification:

- Pytest collection changed from a Windows `UnicodeDecodeError` in SlowAPI configuration parsing to `1531 tests collected`; the regression test passed.
- Backend Ruff, format check, ty, application import, frontend lint/tests/build, identity validation, Alembic single-head/history, and both Compose configurations passed.
- The frontend Prettier check failed on 95 existing files.
- The formal backend pytest/coverage entry point and Alembic upgrade were attempted but blocked by unavailable local PostgreSQL. Docker runtime smoke was blocked by the unavailable Docker daemon.
- Full details and exact results are in [`baselines/T00_BASELINE.md`](baselines/T00_BASELINE.md).

Tests:

- `pytest --collect-only -q`: PASS, 1531 collected.
- Focused limiter regression: PASS, 1 passed.
- `npm --prefix frontend run test`: PASS, 4 files / 11 tests.
- `uv run pytest --cov=app --cov-fail-under=75`: BLOCKED by PostgreSQL connectivity before test execution; no coverage percentage produced.

Migration Changes:

- None. Alembic history was preserved; metadata reports a single head `b7c6d5e4f3a2`.

Configuration Changes:

- Added `app/core/slowapi.env` solely to make SlowAPI configuration decoding deterministic on Windows while preserving `app.core.config` as the reader for application settings.

Known Issues:

- Frontend Prettier check reports 95 files requiring formatting.

Blockers:

- Docker Desktop Linux daemon is unavailable.
- PostgreSQL, Redis, and Qdrant are unavailable on CI-equivalent localhost ports; this prevents required runtime/migration/full-test evidence.

Task Result:

`BLOCKED`

Next Recommended Task:

Restore the local Docker/service environment, collect the missing T00 runtime evidence, then obtain external acceptance before starting `T01`.

## T00-FIX — Complete Reproducible Green Baseline

Started: 2026-09-11
Finished: 2026-09-11

Base Git HEAD: bf0d5b9

Objective:

Re-run the T00 environment-gated checks, remediate the authorized frontend formatting and Docker build-context defects, and record whether the baseline is ready for acceptance.

Files Changed:

- .dockerignore — added minimal build-context exclusions for local environments, dependencies, caches, secrets, tests, documentation, and generated artifacts.
- .gitignore — added the narrow exception required to track .dockerignore.
- frontend/** — ran the repository's standard Prettier formatter; it normalized the 95 files previously reported by format:check, and no frontend content diff remains after Git normalization.
- docs/engineering/baselines/T00_BASELINE.md — replaced stale environment results with current runtime, frontend, and migration evidence.
- docs/engineering/PROJECT_STATE.md, ROADMAP.md, and docs/exec-plans/active/T00.md — synchronized the current blocked state and handoff.
- This execution ledger — appended this T00-FIX record.

Commands Executed:

- docker version; docker compose version; docker ps.
- docker compose config, project-scoped Compose build/start with temporary non-conflicting host ports, service status, container health, HTTP health smoke, logs, and project-scoped cleanup without -v.
- npm --prefix frontend run format; format:check; lint; test; build.
- uv run ruff check app tests; uv run ruff format --check app tests; uv run ty check --error-on-warning app tests; pytest collection and focused limiter regression.
- uv run alembic heads; upgrade head; current; and the formal uv run pytest --cov=app --cov-fail-under=75 entry point against project services.
- Read-only migration graph/database diagnostics and final Git/state checks.

Verification:

- Docker Engine 29.4.3 and Compose 5.1.3 were available. The repository image built with a 4.37 MB context after .dockerignore; the initial context was approximately 230 MB.
- PostgreSQL, Redis, Qdrant, Celery worker, and API became healthy. GET /health returned HTTP 200 with database, Redis, and Qdrant connected.
- Frontend format check, lint, unit tests (4 files / 11 tests), and production build all passed after the authorized formatting-only run.
- Backend Ruff, format check, ty, collection (1531 tests), and focused limiter regression (1 passed) passed.
- Alembic reported one head, b7c6d5e4f3a2, but upgrade head failed at 3a9f8e7b2c1d because relation message_feedbacks does not exist. The formal backend coverage run collected 1531 tests, then produced database fixture errors; no coverage percentage was produced.
- No migration file was changed. A temporary dependency experiment was reverted because the task forbids modifying old migration history. No project volume was deleted; unrelated containers were not changed.

Known Issues:

- Existing Alembic history has an invalid ordering/duplicate feedback-field path. This is a real migration baseline failure, not an environment failure.
- Pytest emitted a non-fatal cache permission warning in the workspace.

Blockers:

- Migration path failure blocks Alembic runtime acceptance and the database-backed backend coverage gate. Resolving it requires an explicitly authorized migration compatibility/graph change consistent with the repository's history policy.

Task Result:

BLOCKED

Next Recommended Task:

Obtain authorization for a migration-history-compatible repair, then rerun Alembic upgrade/current and the complete backend coverage gate. Do not start T01.

## T-INIT — External Acceptance

Accepted: 2026-09-11

Acceptance Source:

Explicit external instruction: `T-INIT: PASS`.

State Transition:

- `last_accepted_task`: `T-INIT`.
- `current_task`: `T00`.
- `current_status`: `IN_PROGRESS`.
- `next_task`: `T01`.
- ROADMAP: T-INIT `PASS`; T00 `IN_PROGRESS`.
- Moved `docs/exec-plans/active/T-INIT.md` to `docs/exec-plans/completed/T-INIT.md`.

Next Recommended Task:

`T00 — Reproducible Green Baseline`

## T-INIT-FIX — Disaster Recovery Decision

Started: 2026-09-11
Finished: 2026-09-11

Base Git HEAD: `bf0d5b9`

Objective:

Append the missing accepted Disaster Recovery decision and synchronize the T-INIT state, roadmap, and active execution plan without changing task acceptance status.

Files Changed:

- `docs/engineering/DECISIONS.md` — appended ADR-020, Disaster Recovery and Restore Verification.
- `docs/engineering/PROJECT_STATE.md` — recorded the Disaster Recovery baseline and fix verification note.
- `docs/engineering/ROADMAP.md` — recorded the T-INIT-FIX scope and preserved task gates.
- `docs/engineering/EXECUTION_LOG.md` — appended this execution record.
- `docs/exec-plans/active/T-INIT.md` — recorded the T-INIT-FIX scope and verification.

Commands Executed:

- `git status --short`
- `git branch --show-current`
- `git rev-parse --short HEAD`
- `git diff --check`
- Read-only ADR/status consistency checks.

Verification:

- ADR-020 exists with `Status: ACCEPTED`.
- T-INIT remains `AWAITING_ACCEPTANCE`.
- T00 remains `NOT_STARTED`.
- State, roadmap, execution log, and active plan are consistent.
- `git diff --check`: PASS.

Known Issues:

- No new issue identified by this documentation-only fix.

Blockers:

- External acceptance remains required before T00.

Task Result:

`AWAITING_ACCEPTANCE`

Next Recommended Task:

`T00 — Reproducible Green Baseline`

## T00-FIX2 - Repair Alembic Migration Chain

Started: 2026-09-11
Finished: 2026-09-11

Base Git HEAD: `bf0d5b9`

Objective:

Repair the historical `message_feedbacks` migration ordering defect without deleting revisions or data, prove empty-database upgrade to the unique head, and complete the backend quality/test/coverage gate.

Files Changed:

- `migrations/versions/3a9f8e7b2c1d_add_feedback_enrichment_fields.py` - moved the feedback enrichment revision after the revision that creates `message_feedbacks`.
- `migrations/versions/c61a28a53622_add_phase3_review_queue_and_token_.py` - removed duplicate feedback and experiment-metrics DDL already owned by ancestor revisions.
- `tests/test_migration_chain.py` - added regression coverage for lineage and duplicate-operation ownership.
- Baseline-only application/test-fixture files - normalized portable paths, tenant-namespaced cache expectations, current auth overrides, deterministic safety/Celery isolation, and required raw-SQL fields.
- T00 state, plan, baseline, and this ledger - synchronized current evidence and status.

Commands Executed:

- Read-only Alembic graph, Git-history, ORM-schema, CI, and test-dependency diagnosis.
- Fresh PostgreSQL `alembic heads`, `upgrade head`, `current`, and schema/index/constraint inspection.
- Migration regression tests, focused regression suites, and `uv run pytest --cov=app --cov-fail-under=75`.
- Ruff, format check, ty, and final Git/state checks.

Verification:

- One Alembic head, `b7c6d5e4f3a2`; a fresh empty PostgreSQL database upgraded successfully and reports that current revision.
- `message_feedbacks` exists with 11 expected columns and six indexes.
- Full backend gate: 1533 passed, 0 failed, 0 skipped, 34 warnings, 79.43% coverage.
- Ruff, format check, and ty passed.

Migration Changes:

- Revision IDs and history were preserved. The repaired dependency is additive; no table or user data is dropped.
- Existing databases already at head execute no operation. Databases at the repaired boundary apply feedback enrichment only after table creation.

Configuration Changes:

- None in T00-FIX2.

Known Issues:

- Optional downgrade from head exposes a pre-existing enum cleanup defect in `4a0032131db6`; required empty-database forward migration is unaffected.
- Pytest emits a non-fatal workspace cache-permission warning.

Blockers:

- None for T00 acceptance gates.

Task Result:

`AWAITING_ACCEPTANCE`

Next Recommended Task:

`T01 - Architecture Guardrails`, only after explicit external acceptance of T00.

## T00 — External Acceptance

Accepted: 2026-09-11

Acceptance Source:

Explicit external instruction in the T01 task: `T00 = PASS`.

State Transition:

- `last_accepted_task`: `T00`.
- `current_task`: `T01`.
- `current_status`: `IN_PROGRESS`.
- `next_task`: `T02`.
- ROADMAP: T00 `PASS`; T01 `IN_PROGRESS`; T02 `NOT_STARTED`.
- Moved `docs/exec-plans/active/T00.md` to `docs/exec-plans/completed/T00.md`.

Next Recommended Task:

Complete `T01 — Architecture Guardrails`; do not start T02.

## T01 — Architecture Guardrails

Started: 2026-09-11
Finished: 2026-09-11

Base Git HEAD: `bf0d5b9`

Objective:

Establish executable structural boundaries for T02–T21 without implementing later enterprise capabilities or restructuring the modular monolith.

Files Changed:

- `docs/architecture/ARCHITECTURE_GUARDRAILS.md` — established the single guardrail source, dependency rules, G1–G12, and the `CURRENT_DEBT` task mapping.
- `docs/engineering/DECISIONS.md` — appended ADR-021 for architecture guardrails and evidence-bound enterprise claims.
- `AGENTS.md` and `docs/explanation/architecture/README.md` — routed structural work to the guardrail source without duplicating it.
- `tests/test_migration_chain.py` — added the exact-one-Alembic-head invariant to the existing lightweight migration graph checks.
- `README.md` — qualified production-readiness/compliance language and the incomplete tenant/RLS boundary.
- Project state, roadmap, execution-plan indexes, T00 archive, T01 active plan, and this ledger — synchronized acceptance and execution memory.

Architecture Findings:

- Confirmed direct commits and Celery dispatch in routes/services, direct task dispatch from graph nodes, HTTP coupling in an application service, concrete Qdrant coupling, and incomplete transaction/tenant/provider seams.
- Recorded these as `CURRENT_DEBT` mapped to T02–T17. No debt remediation, module shell, business-file move, or T02 work was performed.

Verification:

- `git diff --check`: PASS.
- `uv run ruff check app tests`: PASS.
- `uv run ruff format --check tests/test_migration_chain.py`: PASS.
- `uv run ty check --error-on-warning app tests`: PASS.
- `uv run pytest --noconftest tests/test_migration_chain.py -q`: PASS, 3 passed.
- `uv run python scripts/check_project_identity.py`: PASS.
- Guardrail shape/debt mapping check: PASS, G1–G12 and T02–T17 mappings present.

Test-Infrastructure Finding:

- The first focused pytest invocation inherited the global `db_setup` session fixture and failed setup because `.env` points to Compose hostname `db` outside Compose. No test body ran. Re-running this static suite with the established `--noconftest` approach passed all 3 tests. Full pytest was not rerun because no backend implementation changed; accepted T00 evidence remains current.

Migration Changes:

- None. The Alembic graph still has exactly one head, and the new static test enforces that invariant.

Blockers:

- None.

Task Result:

`AWAITING_ACCEPTANCE`

Next Recommended Task:

External acceptance of T01. Do not start T02 before that gate passes.

## T01 — External Acceptance

Accepted: 2026-09-11

Acceptance Source:

Explicit external instruction in the T02 task: `T01 = PASS`.

State Transition:

- `last_accepted_task`: `T01`.
- `current_task`: `T02`.
- `current_status`: `IN_PROGRESS`.
- `next_task`: `T03`.
- ROADMAP: T01 `PASS`; T02 `IN_PROGRESS`; T03 `NOT_STARTED`.
- Moved `docs/exec-plans/active/T01.md` to `docs/exec-plans/completed/T01.md`.

Next Recommended Task:

Complete `T02 — Trusted Request / Task Context`; do not start T03.

## T02 — Trusted Request / Task Context

Completed: 2026-09-11

Status: `AWAITING_ACCEPTANCE`

Objective:

Preserve trusted tenant/user identity, trace/correlation linkage, conversation identity, deterministic idempotency identity, and sanitized data across request-to-Celery boundaries without implementing reliable delivery.

Delivered:

- Added `app/task_runtime` with frozen tenant/system contexts, versioned JSON envelopes, direct-dispatch seam, and worker binding/cleanup lifecycle.
- Migrated every request-side Celery publication under `app` to the seam; a static test prevents future direct `.delay()`/`.apply_async()` calls outside the seam.
- Migrated observability, memory, refund/order, complaint notification, knowledge, evaluation/shadow, and prompt-report workers/callers to validated typed payloads and explicit execution context.
- Propagated existing OpenTelemetry carrier/trace and structured correlation context into workers and child spans without high-cardinality metric labels.
- Removed original chat questions from asynchronous observability, token usage, memory, and evaluation payloads. A real HTTP → message → worker → PostgreSQL regression proves the original phone/email are absent from the task message and stored records.
- Documented the contracts and delivery limitation in `docs/explanation/architecture/task-runtime.md`; updated scoped AGENTS routing/conventions.

Verification:

- Focused T02 suite: PASS, 58 passed.
- Full backend suite: PASS, 1542 passed, 80.12% coverage (required 75%).
- Ruff: PASS.
- Ruff format check: PASS.
- ty: PASS.
- Architecture-specific direct-publication guard: PASS.
- Final `git diff --check`: PASS (line-ending notices only; no whitespace errors).

Environment Notes:

- Docker Desktop stopped during the first full attempt; after restart, Qdrant localhost traffic required the runtime project credential and process-local proxy bypass. The isolated graph-memory suite then passed 4/4 and the complete suite passed.
- No outbox, RabbitMQ, DLQ, consumer receipt, dedupe store, or retry redesign was implemented. Current dispatch is still direct Celery publication and is not reliable-delivery evidence.

Blockers:

None.

Next Recommended Task:

External acceptance of T02. T03 remains `NOT_STARTED` and must not begin before that gate passes.

## T02 — External Acceptance

Accepted: 2026-09-11

Acceptance Source:

Explicit external instruction in the T03 task: `T02 = PASS`.

State Transition:

- `last_accepted_task`: `T02`.
- `current_task`: `T03`.
- `current_status`: `IN_PROGRESS`.
- `next_task`: `T04`.
- ROADMAP: T02 `PASS`; T03 `IN_PROGRESS`; T04 `NOT_STARTED`.
- Moved `docs/exec-plans/active/T02.md` to `docs/exec-plans/completed/T02.md`.

Next Recommended Task:

Complete `T03 — Transactional Outbox`; do not start T04.

## T03 — Transactional Outbox

Completed: 2026-09-12

Status: `AWAITING_ACCEPTANCE`

Objective:

Make critical business state and its required asynchronous intent atomic, then publish the sanitized T02 task envelope through the current Celery transport with truthful at-least-once semantics.

Delivered:

- Added the `outbox_events` model and additive Alembic revision `c8d7e6f5a4b3`, including explicit tenant ownership, typed/sanitized envelope storage, idempotency uniqueness, retry metadata, and expiring claim state.
- Added a flush-only transactional enqueue API that never commits and rejects tenant mismatches or raw phone, email, and original-question payloads.
- Migrated critical refund review/payment/SMS and knowledge indexing call sites so business state and outbox intent share the caller-owned transaction.
- Added the task publisher Port/current Celery adapter and an independently runnable relay with `FOR UPDATE SKIP LOCKED`, short lease transactions, publish-outside-transaction behavior, bounded retry backoff, graceful shutdown, structured logs, and low-cardinality metrics.
- Documented and tested at-least-once behavior: publish success followed by mark failure can duplicate delivery; the event is not lost and retains the same idempotency key for T04 consumer deduplication.

Verification:

- Focused T03/migrated-path suite: PASS, 68 passed.
- Fresh PostgreSQL upgrade: PASS, single head `c8d7e6f5a4b3`; outbox table, constraints, and indexes verified.
- Full backend suite: PASS, 1558 passed, 0 failed, 80.18% coverage (required 75%).
- Ruff: PASS.
- Ruff format check: PASS, 366 files already formatted.
- ty: PASS with `--error-on-warning`.
- Project identity/document links: PASS.

Delivery Semantics:

Business data plus outbox intent is atomic. Outbox-to-broker publication is at-least-once; exactly-once is not claimed.

Blockers:

None.

Next Recommended Task:

External acceptance of T03. T04 remains `NOT_STARTED` and must not begin before that gate passes.

## T03 — External Acceptance

Accepted: 2026-09-12

Acceptance Source:

Explicit external instruction in the T04 task: `T03 = PASS`.

State Transition:

- `last_accepted_task`: `T03`.
- `current_task`: `T04`.
- `current_status`: `IN_PROGRESS`.
- `next_task`: `T05`.
- ROADMAP: T03 `PASS`; T04 `IN_PROGRESS`; T05 `NOT_STARTED`.
- Moved `docs/exec-plans/active/T03.md` to `docs/exec-plans/completed/T03.md`.

Next Recommended Task:

Complete `T04 — RabbitMQ + Reliable Celery`; do not start T05.

## T04 — RabbitMQ + Reliable Celery

Completed: 2026-09-12

Status: `AWAITING_ACCEPTANCE`

Objective:

Make RabbitMQ the Celery broker and make protected critical database handlers safe under duplicate delivery through crash-recoverable receipts, bounded retry classification, and a real terminal DLQ without claiming global exactly-once.

Delivered:

- Added RabbitMQ 3.13 to Compose with environment credentials, health checks, loopback-only development ports, separate worker/Beat/outbox-relay runtime roles, and explicit critical/default/maintenance queues.
- Added additive receipt revision `d9e8f7a6b5c4` with unique tenant/handler/idempotency identity, processing lease, attempts, outcome, failure metadata, and completed timestamp.
- Added the protected consumer seam: TaskEnvelope validation/context binding, PostgreSQL advisory serialization, atomic database effect plus success receipt, completed-duplicate suppression, stale-lease recovery, and low-cardinality outcome metrics.
- Applied per-task reliable ACK/worker-loss policy to critical refund handlers, bounded transient backoff/jitter, permanent failure classification, and durable RabbitMQ DLQ publication that requeues the original message if terminal evidence cannot be stored.
- Made every configured Beat entry carry an explicit system envelope without synthesizing a default tenant; business services remain isolated behind the T03 outbox and TaskPublisher Port.

Verification:

- Targeted T03/T04 suite: PASS, 86 passed.
- RabbitMQ integration: PASS, 3 tests, including connection-loss redelivery and Outbox -> RabbitMQ -> worker duplicate-safe execution.
- Fresh PostgreSQL 16 upgrade: PASS, single head `d9e8f7a6b5c4`; receipt table, unique identity constraint, and recovery index verified.
- Full backend suite: PASS, 1574 passed, 0 failed, 80.38% coverage (required 75%).
- Ruff: PASS. Ruff format check: PASS, 373 files. ty: PASS with `--error-on-warning`.
- Compose syntax, RabbitMQ health, project identity/local links, and `git diff --check`: PASS.

Semantics:

Outbox publication is at-least-once. Protected database-local handlers are duplicate-safe for their receipt identity. Global exactly-once is not claimed; external providers without idempotency support may still observe duplicate requests.

Blockers:

None.

Next Recommended Task:

External acceptance of T04. T05 remains `NOT_STARTED` and must not begin before that gate passes.

## T04 — External Acceptance

Accepted: 2026-09-12

Acceptance Source:

Explicit external instruction in the T05-IMPLEMENT task: `T04 = PASS`.

State Transition:

- `last_accepted_task`: `T04`.
- `current_task`: `T05`.
- `current_status`: `IN_PROGRESS`.
- `execution_stage`: `IMPLEMENT`.
- `next_task`: `T06`.
- ROADMAP: T04 `PASS`; T05 `IN_PROGRESS`; T06 `NOT_STARTED`.
- Moved `docs/exec-plans/active/T04.md` to `docs/exec-plans/completed/T04.md`.

Next Recommended Task:

Complete T05 implementation and targeted verification only; do not run full verification or start T06.

## T05-IMPLEMENT — Memory Consistency Implementation

Completed: 2026-09-12

Status: `IN_PROGRESS`

Execution Stage: `VERIFY_PENDING`

Objective:

Make PostgreSQL authoritative for structured summaries and Qdrant a recoverable derived index without a distributed transaction or exactly-once claim.

Delivered:

- Added version/tombstone state and additive revision `e3f4a5b6c7d8` for authoritative interaction summaries.
- Replaced the summary flush plus direct Qdrant dual write with one PostgreSQL transaction containing the summary/tombstone and a PII-free Outbox event carrying only memory ID, version, and operation.
- Added reliable `memory.sync_vector` consumption using the T04 receipt store, an external-operation lease committed before Qdrant I/O, stable Qdrant point identity, stale-event rejection, delete retry, and critical-queue routing.
- Added tenant-scoped reconciliation and explicit vector-recall degradation while preserving PostgreSQL-backed memory reads.
- Documented ADR-022 and updated scoped model/task/runtime/memory guidance.

Targeted Verification:

- T05 memory plus shared receipt regression set: PASS, 43 passed.
- Scoped Ruff: PASS. Scoped Ruff format check: PASS, 14 files. Scoped ty: PASS with `--error-on-warning`.
- Migration import/compile sanity: PASS; Alembic reports one head, `e3f4a5b6c7d8`.

Deferred by Stage Contract:

- Full backend pytest/coverage.
- Repository-wide Ruff, format check, and ty.
- Fresh PostgreSQL database upgrade and schema inspection.

Blockers:

None.

Next Recommended Task:

Run T05-VERIFY only. T05 remains `IN_PROGRESS`; T06 remains `NOT_STARTED`.

## T05-VERIFY — Memory Consistency Verification

Completed: 2026-09-12

Status: `AWAITING_ACCEPTANCE` — `EXTERNAL_ACCEPTANCE_PENDING`

Verification evidence:

- T05 targeted and migration-chain regressions: 48 passed.
- Repository-wide Ruff check, format check, and ty: PASS.
- Full backend gate: 1583 passed, 3 skipped, 80.45% coverage; required 75% reached.
- Fresh temporary PostgreSQL database upgraded successfully through single Alembic head `e3f4a5b6c7d8`.
- Real RabbitMQ unacknowledged-delivery redelivery smoke: PASS.
- Real Outbox → RabbitMQ → Celery worker duplicate-safe smoke: PASS.
- Authenticated local Qdrant-backed backend tests: PASS. Qdrant failure/recovery, duplicate/stale protection, delete consistency, and tenant isolation targeted tests: PASS.

Environment note:

- Local verification required explicit loopback PostgreSQL/Redis/Qdrant endpoints and `NO_PROXY/no_proxy` for localhost; no source architecture change was made for this environment routing issue.

State transition:

- T05 is `AWAITING_ACCEPTANCE` pending external acceptance.
- `execution_stage` is `EXTERNAL_ACCEPTANCE_PENDING`.
- T06 remains `NOT_STARTED` and must not begin.

## T05 — External Acceptance

Accepted: 2026-09-12

Acceptance Source:

Explicit external instruction in the T06-IMPLEMENT task: `T05 = PASS`.

State Transition:

- `last_accepted_task`: `T05`.
- `current_task`: `T06`.
- `current_status`: `IN_PROGRESS`.
- `execution_stage`: `IMPLEMENT`.
- `next_task`: `T07`.
- ROADMAP: T05 `PASS`; T06 `IN_PROGRESS`; T07 `NOT_STARTED`.
- Moved `docs/exec-plans/active/T05.md` to `docs/exec-plans/completed/T05.md`.

Next Recommended Task:

Complete T06 implementation and targeted verification only; do not run the full backend suite or start T07.

## T06-IMPLEMENT — Tenant Hardening Implementation

Completed: 2026-09-12

Status: `IN_PROGRESS`

Execution Stage: `VERIFY_PENDING`

Delivered:

- Added a minimal operational Tenant domain, canonical status resolver, and fail-closed request/worker TenantContext binding without changing the existing string tenant IDs.
- Added revision `f4a5b6c7d8e9` with idempotent tenant backfill and removal of implicit tenant defaults; no RLS policy was added.
- Strengthened ORM read, instance/bulk mutation, and cross-tenant relationship protection.
- Unified Redis tenant/system namespaces and cleanup; unified Qdrant tenant payload/query/delete seams across knowledge, memory, product, and PII paths.
- Kept knowledge synchronization inside the resolved task context and namespaced active local uploads; S3/object storage is documented as not currently active.
- Added the T07-ready tenant-owned/global table inventory in `docs/architecture/TENANCY.md`.

Targeted Verification:

- T06 targeted regressions: PASS, 60 tests; final corrected ORM/Qdrant subset: PASS, 3 tests.
- Scoped Ruff: PASS. Scoped Ruff format check: PASS. Scoped ty: PASS with `--error-on-warning`.
- Alembic single head: PASS, `f4a5b6c7d8e9`.

Deferred by Stage Contract:

- Full backend pytest/coverage.
- Repository-wide Ruff, format check, and ty.
- Fresh PostgreSQL database upgrade and schema/constraint inspection.

Blockers:

None.

Next Recommended Task:

Run T06-VERIFY only when explicitly requested. T07 remains `NOT_STARTED`.

## T06-VERIFY — Tenant Hardening Verification

Completed: 2026-09-12

Status: `NEEDS_EVIDENCE`

Execution Stage: `VERIFY_PENDING`

Verification evidence:

- T06 critical tenant rerun was environment-blocked. The configured Compose hosts `db` and `redis` did not resolve; loopback PostgreSQL async connections timed out, and the Redis/Qdrant fixtures did not complete. The critical run ended with 84 setup errors before test bodies; no tenant isolation assertion failed.
- Full `uv run pytest --cov=app --cov-fail-under=75` collected 1600 tests but did not produce final counts or coverage before safe termination after prolonged infrastructure setup waits.
- Repository-wide Ruff, Ruff format check, and `ty check --error-on-warning` passed after four obvious test calls were given the required `tenant_id="default"` argument. No runtime code was changed.
- Static migration graph checks passed and Alembic reports one head: `f4a5b6c7d8e9`. Fresh PostgreSQL upgrade/backfill/schema inspection could not run without a disposable database connection.
- Tenant inventory readiness is `YES`: static table classification passed with no ambiguous SQLModel tables. No RLS work was performed.

Unique blocker:

- The local verification infrastructure cannot complete PostgreSQL, Redis, or Qdrant connections, and Docker API access is unavailable. T06 remains `NEEDS_EVIDENCE`; T07 remains `NOT_STARTED`.

## T06-VERIFY-RETRY — Tenant Hardening Runtime Evidence

Completed: 2026-09-12

Status: `NEEDS_EVIDENCE`

Execution Stage: `VERIFY_PENDING`

Evidence:

- Existing Compose services were restored on temporary non-conflicting host ports. PostgreSQL, Redis, and Qdrant were healthy and reachable from host and application-network probes; unrelated containers and volumes were preserved.
- T06 critical tenant suite: 84 passed, 14 warnings. Tenant resolution/fail-closed, ORM read/write/relationship, Redis namespace/cleanup, Qdrant query/delete, TaskContext, and T05 memory/vector isolation passed.
- Fresh PostgreSQL migration: PASS. Empty database upgrade succeeded through the single head `f4a5b6c7d8e9`; tenant/backfill/default-column checks passed.
- Full backend gate: 1573 passed, 3 skipped, 11 failed, 13 errors, 78.49% coverage. The 75% threshold was reached, but the gate is not green. Remaining failures are outside the T06 critical isolation set and are classified as stale test fixtures, direct dependency invocation, registration transaction behavior, Windows event-loop cleanup, and one documentation link.
- Previously proven Ruff, format, ty, and RLS inventory checks were not repeated. No runtime code, architecture, RLS, OIDC/RBAC, or T07 work was performed.

State transition:

- T06 remains `NEEDS_EVIDENCE` at `VERIFY_PENDING` because the full backend gate is not green.
- T07 remains `NOT_STARTED`.

## T06-FIX-IMPLEMENT — Regression Fixture & Windows Async Repair

Completed: 2026-09-12

Status: `BLOCKED`

Execution Stage: `VERIFY_PENDING`

Evidence:

- Context recovery confirmed T06 `BLOCKED`, T07 `NOT_STARTED`, and M01 repository consolidation present. PostgreSQL, Redis, Qdrant, and RabbitMQ preflight passed.
- Before editing, the historical regression nodes were rerun with M01 test isolation: 3 passed, 10 failed, and 11 errored. Documentation-link regression passed.
- Registration analysis proved a core production transaction-semantics defect: the route resolves the tenant and opens a transaction, `register_user()` only flushes, `get_session()` does not commit on exit, and an independent session cannot observe the created user.
- Per contract, Terra stopped and made no code/test fixture changes. Full backend and static checks were not run.

Escalation:

- `CORE_TRANSACTION_SEMANTICS_REQUIRES_SOL`
- Stale tenant fixtures, direct dependency invocation, and Windows async lifecycle remain unmodified and unverified for repair because the required registration escalation stops this task.
- T07 remains `NOT_STARTED`.

## M01 — Repository Consolidation & Legacy Cleanup

Completed: 2026-09-12

Status: `AWAITING_ACCEPTANCE`

M01 Repository Consolidation completed.

Evidence:

- Preserved the extensive pre-existing T00–T06 worktree and left T06/T07 status unchanged.
- Classified every cleanup candidate in `docs/engineering/REPOSITORY_CLEANUP.md` before
  deletion. Removed three proven obsolete files: `Dockerfile.save`, `start.sh`, and
  `celery_worker.py`; all ambiguous candidates remain `REVIEW`.
- Consolidated README, documentation authority, Compose naming/ports, environment ownership,
  RabbitMQ/Redis roles, CI test transports, test storage isolation, monitoring scripts, and
  shell line endings.
- Both Compose configurations, focused Ruff/format/ty, 24 targeted tests, YAML parsing,
  Bash syntax, project identity/local links, environment inventory, and `git diff --check`
  passed.
- Runtime smoke verified healthy project-scoped RabbitMQ and Compose DNS. Unrelated legacy
  `ecommerce_*` containers blocked standard PostgreSQL/Redis/Qdrant/API ports and were not
  stopped or deleted; no volumes were removed.

State transition:

- M01: `IN_PROGRESS` → `AWAITING_ACCEPTANCE`.
- T06 remains `NEEDS_EVIDENCE / VERIFY_PENDING`.
- T07 remains `NOT_STARTED`.

## T06-REGRESSION-RECHECK — M01 Historical Failure Recheck

Completed: 2026-09-12

Status: `BLOCKED`

Execution Stage: `VERIFY_PENDING`

Evidence:

- M01 repository consolidation is present. Its isolated test configuration was used: `test_` PostgreSQL database, Redis DB 15, process-scoped Qdrant collection, and memory Celery transport defaults.
- PostgreSQL, Redis, Qdrant, and RabbitMQ preflight probes passed.
- Historical T06 regression nodes were rerun before any full suite: 3 passed, 10 failed, and 11 errored.
- Remaining categories: stale tenant fixtures (performance/task reliability/chat/WebSocket), direct dependency invocation (`test_revoked_token_is_rejected_immediately`), registration transaction behavior (`test_register_success_creates_user_and_returns_token`), and Windows async event-loop cleanup. The documentation-link node passed in this recheck.
- No T06 cross-tenant isolation failure was observed. No architecture, RLS, OIDC/RBAC, or T07 work was performed.

State transition:

- T06 remains `BLOCKED` because the historical regression recheck is not green.
- T07 remains `NOT_STARTED`.

## T06-FIX-TX - Registration Transaction Boundary

Completed: 2026-09-12

Status: `BLOCKED`

Execution Stage: `TX_FIXED_FIXTURES_PENDING`

Evidence:

- End-to-end ownership tracing confirmed that tenant resolution implicitly began the request transaction, while `AuthService.register_user()` selected a flush-only branch and `get_session()` closed without committing. The registration endpoint could therefore return a token response for state that was not durable.
- The existing independent-session visibility test reproduced the defect before repair: the endpoint returned `200`, but Session B found no user.
- The registration route/application use case now owns one explicit transaction. Successful context exit commits before response return; exceptional exit rolls back. `AuthService.register_user()` is a nested query/add/flush/refresh collaborator.
- Durable success, forced failure rollback, duplicate/conflict atomicity, directly related auth/registration regressions, and tenant fail-closed checks passed: 27 tests.
- Scoped Ruff, Ruff format check, and `ty check --error-on-warning` passed for the three modified Python files.
- No repository/service commit, global session dependency change, Tenant Architecture change, RLS work, or T07 work was introduced. The full backend suite was not run.

State transition:

- T06 remains `BLOCKED`; execution stage is `TX_FIXED_FIXTURES_PENDING`.
- Remaining blockers: stale tenant fixtures, direct dependency invocation fixture, and Windows event-loop cleanup.
- T07 remains `NOT_STARTED`.

## T06-FIX-FIXTURES - Test Fixtures & Windows Async Runtime

Completed: 2026-09-12

Status: `BLOCKED`

Execution Stage: `VERIFY_PENDING`

Scope:

- Repair only the remaining T06 regression fixtures and Windows WebSocket async lifecycle. Registration transaction architecture was not revisited.

Evidence:

- Context recovery confirmed the existing M01-isolated test setup, T06 `BLOCKED`, and T07 `NOT_STARTED`; PostgreSQL, Redis, Qdrant, and RabbitMQ preflight was already green.
- Canonical `active_tenant` and `tenant_context` fixtures now create a committed active tenant, bind it explicitly, and clean the context/tenant deterministically. The stale chat/performance/task nodes passed: 16 tests.
- `test_revoked_token_is_rejected_immediately` now supplies its real `AsyncSession`; the valid-token companion passed, and the revoked-token test passed without changing the production dependency.
- WebSocket security tests use a persistent TestClient portal and a per-client `NullPool` async engine/session maker; engine disposal is scheduled on the owning portal loop. The WebSocket security class passed: 6 tests, including all three historical event-loop failures.
- Minimal tenant fail-closed smoke and durable registration smoke passed; combined with the revoked-token and WebSocket checks, this safety set passed: 11 tests.
- Affected-file Ruff, Ruff format check, and `ty check --error-on-warning` passed. The shared synchronous DB fixture now rolls back only active transactions during cleanup, avoiding deassociated-transaction warnings.
- Production behavior was unchanged: no default-tenant fallback, auth revocation bypass, tenant isolation exception, RLS, OIDC/RBAC, or T07 work was introduced.

Transaction/lifecycle notes:

- Transaction owner: unchanged from T06-FIX-TX; the registration route/application use case owns the explicit transaction boundary.
- The fixture repair owns only test tenant setup/context lifecycle and the WebSocket test engine/pool lifecycle; no repository hidden commits and no global session dependency changes were introduced.

State transition:

- T06 remains `BLOCKED` with `execution_stage: VERIFY_PENDING` because the full backend suite has not been rerun after these targeted repairs.
- T07 remains `NOT_STARTED`.

## M01 - External Acceptance

Accepted: 2026-09-12

Acceptance Source:

Explicit user instruction in T06-FINAL-VERIFY: M01 repository consolidation is externally accepted.

State transition:

- M01 moved from `AWAITING_ACCEPTANCE` to `PASS`.
- Its plan moved from `docs/exec-plans/active/M01.md` to `docs/exec-plans/completed/M01.md`.
- T06/T07 scope and gate order were unchanged.

## T06-FINAL-VERIFY - Final Full Regression

Completed: 2026-09-12

Status: `AWAITING_ACCEPTANCE`

Execution Stage: `EXTERNAL_ACCEPTANCE_PENDING`

Evidence:

- Context recovery confirmed the T06/T07 gate order; the current branch is `main` at `bf0d5b9`, with the pre-existing uncommitted worktree preserved.
- PostgreSQL, Redis, Qdrant, and RabbitMQ preflight passed on the M01 host-endpoint test setup; PostgreSQL used dedicated database `test_knowledge_base` and Qdrant used the run-scoped test collection configuration.
- The first invocation exposed a host loopback proxy routing issue for authenticated Qdrant requests. A read-only probe reproduced it, and the same probe passed with `NO_PROXY/no_proxy=127.0.0.1,localhost`; no repository or production code was changed.
- The canonical full backend gate passed with the corrected host environment: 1607 collected, 1604 passed, 0 failed, 0 errors, 3 skipped, 80.58% coverage, elapsed 906.41 seconds.
- `uv run alembic heads` passed with the single expected head `f4a5b6c7d8e9`; no migration history changed during FINAL-VERIFY.
- Existing repository-wide Ruff, format, and ty evidence and the latest affected-file static evidence remain PASS. Tenant hardening, registration transaction, fixture repair, and Windows WebSocket runtime regressions remain PASS.
- No architecture redesign, RLS, OIDC/RBAC, or T07 work was performed.

State transition:

- T06 moved from `BLOCKED / VERIFY_PENDING` to `AWAITING_ACCEPTANCE / EXTERNAL_ACCEPTANCE_PENDING`.
- T07 remains `NOT_STARTED`.

## T06 - External Acceptance

Accepted: 2026-09-12

Acceptance Source:

Explicit user instruction in T07-IMPLEMENT: `T06 = PASS`.

State transition:

- T06 moved from `AWAITING_ACCEPTANCE` to `PASS`.
- Its plan moved from `docs/exec-plans/active/T06.md` to `docs/exec-plans/completed/T06.md`.
- T07 moved from `NOT_STARTED` to `IN_PROGRESS` at execution stage `IMPLEMENT`.
- T08 remains `NOT_STARTED`.

## T07-IMPLEMENT - PostgreSQL Row-Level Security Start

Started: 2026-09-12

Recovery evidence:

- Branch `main`, recovery HEAD `bf0d5b9`; extensive pre-existing T00-T06/M01 worktree changes are preserved.
- The accepted T06 inventory classifies 39 tenant-owned tables and the global/system `tenants` and `alembic_version` tables with no ambiguity.
- Canonical `tenant_id` remains `VARCHAR(64)`; all tenant-owned tables already have a tenant index, and proven tenant-local unique constraints are already composite.
- Current runtime and migration database credentials are not yet separated, and local runtime commonly uses PostgreSQL `postgres`; T07 must remove this RLS-bypass condition and prove the effective runtime role on real PostgreSQL.
- T07 is `IN_PROGRESS` at `IMPLEMENT`; T08 remains `NOT_STARTED`.

## T07-IMPLEMENT - PostgreSQL Row-Level Security Completion

Completed: 2026-09-13

Status: `IN_PROGRESS`

Execution Stage: `VERIFY_PENDING`

Implementation:

- Added centralized async/sync SQLAlchemy binding of transaction-local
  `app.current_tenant_id` and a fixed runtime or maintenance database capability role, sourced from
  the accepted T06 `TenantContext`; missing runtime context fails closed and pooled transactions
  receive an explicit empty local setting.
- Added additive migration `a5b6c7d8e9f0` after `f4a5b6c7d8e9`, enabling and forcing RLS with an
  `ALL` policy containing `USING` and `WITH CHECK` across the exact 39-table T06 inventory.
- Added least-privilege login provisioning from existing settings conventions. Alembic uses the
  admin URL; API/tenant workers use runtime capability; outbox and separately routed scheduled
  maintenance use the isolated maintenance capability. Application `SUPER_ADMIN` does not select
  or inherit database maintenance access.
- Preserved application-level tenant predicates/guards and canonical `VARCHAR(64)` tenant IDs; no
  tenant uniqueness, index, or data migration was required.

Targeted verification:

- Real PostgreSQL RLS integration: PASS, 9 tests. Raw cross-tenant read, direct-ID
  read/update/delete, cross-tenant insert, missing context, pooled A -> B -> none isolation, worker
  propagation, runtime-role reality, maintenance separation, and catalog inventory passed.
- Existing T06 application tenant guard subset: PASS, 16 tests. Migration-chain guard: PASS, 7
  tests. Compose/Celery startup and database-capability separation: PASS, 8 tests. Dedicated
  credential fail-closed configuration: PASS, 4 tests.
- Scoped Ruff, Ruff format check, and ty with `--error-on-warning`: PASS. Alembic reports the single
  head `a5b6c7d8e9f0`; Python compile/import and Compose config checks passed.
- Normal runtime escape-hatch audit: PASS; no `row_security=off`, privileged runtime URL,
  superuser/table-owner execution, `BYPASSRLS`, admin-credential fallback, or RBAC-selected
  maintenance path was found. Administrator reuse is confined to explicitly named `test_`
  databases for fixture compatibility.

Environment notes:

- An early provisioning run exposed an asyncpg DDL-parameter type error; explicit text casts fixed
  it before the final passing PostgreSQL run.
- The existing `test_knowledge_base` schema/Alembic state is inconsistent and was not accepted as
  upgrade-from-current-head evidence. A disposable PostgreSQL 16 database migrated to the new head
  and passed all targeted RLS gates; clean upgrade evidence remains for Luna verification.

State transition:

- T06 remains externally accepted `PASS`.
- T07 remains `IN_PROGRESS` and moves from `IMPLEMENT` to `VERIFY_PENDING`.
- T08 remains `NOT_STARTED`.
- Full backend regression, independent fresh migration, upgrade-from-current-head migration, and
  final runtime integration remain for the Luna verification stage.

## T07-VERIFY - PostgreSQL Row-Level Security Final Verification

Completed: 2026-09-13

Status: `NEEDS_EVIDENCE`

Execution Stage: `VERIFY_BLOCKED`

Evidence:

- Preflight passed: Docker Compose config, PostgreSQL, Redis, RabbitMQ, and Qdrant health checks.
- Fresh disposable PostgreSQL migration passed to `a5b6c7d8e9f0`; actual catalog inspection returned
  `39 expected / 39 found / 39 forced / 39 protected`.
- Upgrade-path database passed from accepted `f4a5b6c7d8e9` to `a5b6c7d8e9f0`; seeded Tenant A/B
  rows were preserved, runtime raw access saw only A, B mutation was blocked, and pooled A -> B ->
  no-context isolation passed.
- A real RabbitMQ/Celery worker task using the runtime login and TaskEnvelope returned only the
  bound Tenant A row. Runtime/maintenance separation and no-assume checks passed.
- `uv run alembic heads` passed with one head `a5b6c7d8e9f0`; implementation-thread Ruff/format/ty
  evidence remains valid because VERIFY made no implementation changes.

Full backend regression:

- `uv run pytest --cov=app --cov-fail-under=75` collected 1621 items and ended with 30 passed, 0
  failed, 1591 errors, 0 skipped, 40.64% coverage, elapsed 2350.20s.
- Root failure: the shared `_truncate_leaky_tables` fixture executes `TRUNCATE TABLE
  task_execution_receipts, ...` through the runtime capability and PostgreSQL returns
  `asyncpg.exceptions.InsufficientPrivilegeError: permission denied for table task_execution_receipts`.
- Classification: `REGRESSION` (test fixture/least-privilege mismatch). No RLS redesign or tracked
  implementation change was made in this VERIFY thread.

State transition:

- T06 remains externally accepted `PASS`.
- T07 moves from `IN_PROGRESS / VERIFY_PENDING` to `NEEDS_EVIDENCE / VERIFY_BLOCKED`.
- T08 remains `NOT_STARTED`.
- A focused FIX task must make test cleanup compatible with production least privilege, then rerun
  the full backend gate before T07 can be externally accepted.

## T07-FIX-TEST-CLEANUP - Test database cleanup privilege separation start

Started: 2026-09-13

Status: `IN_PROGRESS`

Execution Stage: `FIX_IMPLEMENT`

Recovery confirmed T06 `PASS`, T07 blocked by the shared cleanup fixture's runtime-role `TRUNCATE`,
and T08 `NOT_STARTED`. The repair is limited to an explicit trusted test-maintenance connection;
runtime credentials, RLS policies, and production role privileges are not in scope.

## T07-FIX-TEST-CLEANUP - Test database cleanup privilege separation completion

Completed: 2026-09-13

Status: `BLOCKED`

Execution Stage: `VERIFY_PENDING`

Implementation and evidence:

- Refactored `_truncate_leaky_tables` to use an explicit session-scoped
  `test_maintenance_engine` backed by `MIGRATION_DATABASE_URL` for trusted test-harness cleanup.
  It preserves the intentional table list and `RESTART IDENTITY CASCADE` behavior and does not
  bind a fake tenant context.
- Added database-safety regression guards: the maintenance cleanup succeeds, while a
  production-like runtime session is denied `TRUNCATE` on `task_execution_receipts`.
- Disposable PostgreSQL targeted gates passed: `2` cleanup/privilege guards, `5` representative
  task receipt/chat/auth/memory/task samples, and `1` raw cross-tenant RLS smoke.
- Changed-test Ruff, format check, and ty passed. PostgreSQL role inspection confirmed the
  temporary runtime and maintenance logins are non-superuser, non-BypassRLS, non-CREATEDB,
  non-CREATEROLE, and only members of their intended fixed capability roles.
- No production RLS policy, migration, runtime grant, or application architecture changed.

State transition:

- T07 remains `BLOCKED` at `VERIFY_PENDING` because the full backend regression has not been rerun.
- T08 remains `NOT_STARTED`; no later task was started.

## T07-FINAL-VERIFY - Final RLS regression gate

Completed: 2026-09-13

Status: `BLOCKED`

Execution Stage: `VERIFY_PENDING`

Evidence:

- Preflight passed: PostgreSQL, Redis, RabbitMQ, Qdrant, and Compose configuration. The full run
  used isolated `test_t07_final_regression`, runtime login `t07_final_runtime`, Redis DB 15, and a
  run-scoped Qdrant collection. RabbitMQ tests skipped without `T04_RABBITMQ_URL`, as designed.
- Both test privilege guards passed before the suite: maintenance cleanup succeeded and the
  runtime session (effective role `star_warehouse_runtime`) was denied `TRUNCATE`.
- Full command `uv run pytest --cov=app --cov-fail-under=75` collected `1623`, with `1618 passed`,
  `2 failed`, `3 skipped`, `80.73%` coverage, and `998.74s` pytest elapsed (`1022.80s` shell time).
  The previous runtime-role cleanup cascade is fixed and did not recur.
- `tests/graph/test_memory_integration.py::test_memory_node_routes_to_supervisor` failed as
  `RLS_REGRESSION`: `_refresh_database_tenant_context` makes concurrent structured-memory queries
  race while provisioning one `AsyncSession`, yielding `InvalidRequestError` and a missing
  `structured_facts` field.
- `tests/performance/test_performance.py::test_cache_reduces_latency` failed as
  `PRE_EXISTING_OTHER`: full-run timing was `2.3749ms` hit versus `2.1214ms` miss; isolated rerun
  passed, indicating benchmark jitter rather than cleanup/RLS behavior.
- `alembic heads` remains the single head `a5b6c7d8e9f0`; FINAL_VERIFY made no tracked code,
  migration, or privilege changes, so existing Ruff/format/ty PASS evidence is inherited.

State transition:

- T07 remains `BLOCKED` at `VERIFY_PENDING`; no external acceptance transition occurred.
- T08 remains `NOT_STARTED` and was not started.

## T07-FIX-RLS-CONCURRENCY - Concurrent RLS Context Binding Repair

Completed: 2026-09-13

Status: `BLOCKED`

Execution Stage: `VERIFY_PENDING`

Findings and implementation:

- The exact defect was A+B: `build_memory_node` shared one `AsyncSession` across four independent
  `asyncio.gather` reads, whose first ORM operations concurrently reached
  `_refresh_database_tenant_context` while connection/transaction provisioning was in progress.
  The stable-transaction guard already prevented repeated binding SQL, so C was not the root cause.
- Each concurrent structured-memory read now owns an independent session and explicit transaction.
  The trusted tenant ContextVar is bound with `SET LOCAL` by `after_begin`; refresh does not eagerly
  provision a connection and remains available for a trusted tenant resolved after an existing
  transaction began.
- An explicit caller-owned session is retained as a compatibility seam and is used only for ordered
  reads inside its transaction. No global/per-process lock, retry, sleep, default tenant,
  maintenance credential, RLS bypass, or memory-consistency redesign was introduced.

Evidence:

- Original memory integration failure and session-ownership regression: `2 passed`.
- Disposable real-PostgreSQL targeted gates: `5 passed` — concurrent same-tenant structured reads,
  concurrent cross-tenant structured reads, pooled A -> B -> no-context isolation, raw unfiltered
  RLS isolation, and worker TaskContext propagation.
- Same/cross-tenant concurrency observed only the runtime capability role and returned only the
  corresponding tenant facts. Scoped Ruff, Ruff format check, and ty `--error-on-warning` passed.
- The unrelated performance timing test was neither modified nor run. The full backend suite was
  not run, per task instruction.

State transition:

- T07 remains `BLOCKED` and returns to `VERIFY_PENDING`; full regression remains pending.
- T08 remains `NOT_STARTED` and was not started.

## T07-FINAL-VERIFY-RECHECK - Final Full Regression

Completed: 2026-09-13

Status: `AWAITING_ACCEPTANCE`

Execution Stage: `EXTERNAL_ACCEPTANCE_PENDING`

Preflight and safety smoke:

- PostgreSQL, Redis, RabbitMQ, and Qdrant were reachable/healthy. Isolated settings selected
  `test_star_warehouse_ai`, Redis DB 15, a process-scoped Qdrant collection, runtime capability for
  application sessions, the explicit migration/admin URL for cleanup, and the in-memory broker
  because no dedicated `T04_RABBITMQ_URL` was configured.
- Runtime `TRUNCATE` denial, maintenance cleanup, the original memory integration regression, and
  the concurrent same-tenant memory regression passed.

Full regression:

- `uv run pytest --cov=app --cov-fail-under=75` passed: `1626 collected`, `1623 passed`, `0 failed`,
  `0 errors`, `3 skipped`, `80.67%` coverage, and `970.62s` pytest elapsed (`16:10`).
- The performance timing test passed in the full run and was not modified.

Migration/static:

- `uv run alembic heads` passed with the single expected head `a5b6c7d8e9f0`.
- Ruff, format, and ty remain inherited PASS evidence because no implementation files were modified
  during final verification.

State transition:

- T07 moved from `BLOCKED / VERIFY_PENDING` to `AWAITING_ACCEPTANCE /
  EXTERNAL_ACCEPTANCE_PENDING`; explicit external acceptance is still required before `PASS`.
- T08 remains `NOT_STARTED` and was not started.

## T07 - External Acceptance

Accepted: 2026-09-13

Acceptance Source:

Explicit user instruction in T08-IMPLEMENT: `T07 = PASS`.

State transition:

- T07 moved from `AWAITING_ACCEPTANCE` to `PASS`.
- Its plan moved from `docs/exec-plans/active/T07.md` to
  `docs/exec-plans/completed/T07.md`.
- T08 moved from `NOT_STARTED` to `IN_PROGRESS` at execution stage `IMPLEMENT`.
- T09 and T10 remain `NOT_STARTED`.

## T08-IMPLEMENT - Enterprise Identity Start

Started: 2026-09-13

Recovery evidence:

- Branch `main`, recovery HEAD `bf0d5b9`; extensive pre-existing T00-T07/M01 worktree changes are
  preserved.
- Local password authentication and existing application JWT issuance are retained.
- The legacy enterprise endpoint validates only through UserInfo and then resolves a local user by
  email; it does not persist `issuer + subject` or implement authorization-code state, nonce, PKCE,
  discovery, or JWKS verification.
- T08 is `IN_PROGRESS` at `IMPLEMENT`; T09 and T10 remain `NOT_STARTED`.

## T08-IMPLEMENT - Enterprise Identity Complete

Completed: 2026-09-13

Status: `IN_PROGRESS`

Execution Stage: `VERIFY_PENDING`

Implementation:

- Preserved local credentials and existing application JWT issuance while adding a normalized,
  authority-free principal for local and generic OIDC authentication.
- Added durable global `issuer + subject` external bindings, fail-closed and explicitly gated
  verified-email first linking, database uniqueness/concurrency handling, active-user checks, and
  no implicit tenant/role/scope creation.
- Added discovery, cached JWKS rotation, asymmetric ID-token validation, authorization-code
  exchange, single-use state, nonce, PKCE S256, stable errors, non-sensitive audit events, and an
  optional DEV-only Keycloak Compose profile.

Evidence:

- Final targeted identity/auth/revocation/migration selection: `40 passed` in `25.65s`.
- Real Keycloak discovery, JWKS, RS256 token validation, and issuer/subject resolution: PASS;
  browser E2E is not claimed.
- Fresh disposable PostgreSQL upgrade and catalog inspection: PASS; Alembic has the single head
  `b6c7d8e9f0a1`, and no historical migration was modified.
- Scoped Ruff, format check, and ty: PASS. Compose identity profile, realm JSON, and targeted diff
  hygiene: PASS.
- Initial failed invocations were discarded as test-environment evidence: Compose-only DNS,
  stale disposable credentials, and loopback proxy routing were corrected without production-code
  workarounds.

State transition:

- T08 remains `IN_PROGRESS` and moves from `IMPLEMENT` to `VERIFY_PENDING`.
- T09 and T10 remain `NOT_STARTED`; neither task was started.
- The complete backend and frontend suites were not run, per the IMPLEMENT-stage constraint.

## T08-FINAL-VERIFY - Enterprise Identity final verification

Completed: 2026-09-13

Status: `AWAITING_ACCEPTANCE`

Execution Stage: `EXTERNAL_ACCEPTANCE_PENDING`

Recovery and preflight:

- Recovery confirmed T07 `PASS`, T08 `IN_PROGRESS / VERIFY_PENDING`, and T09 `NOT_STARTED` on
  branch `main` at `bf0d5b9`. Existing uncommitted T00-T08 work was preserved.
- Base Compose and `identity` profile configuration both passed. The disposable PostgreSQL
  service accepted SQL connections; canonical RabbitMQ and the DEV-only Keycloak service were
  running, the Keycloak realm endpoint returned 200, OIDC discovery returned the configured issuer,
  and JWKS returned two keys.

Identity data boundary:

- `external_identities` is confirmed `TENANT_OWNED`, not global identity: the actual fresh schema
  includes `tenant_id`, a local-user foreign key, tenant/user indexes, global `(issuer, subject)`
  uniqueness, forced RLS, and the expected `USING`/`WITH CHECK` policy.
- The actual runtime capability saw a binding in tenant A and zero rows in tenant B. No implicit
  tenant access or tenant selection was created by identity resolution.

Migration and compatibility gates:

- A newly created disposable database upgraded successfully to `b6c7d8e9f0a1`; catalog inspection
  verified the external identity table, issuer, subject, user relationship, indexes, unique
  constraint, and forced RLS.
- A separate database at `a5b6c7d8e9f0` upgraded successfully to `b6c7d8e9f0a1`. A seeded local
  user was preserved and authenticated through the existing local-auth/JWT path.
- `alembic heads` reports exactly one head: `b6c7d8e9f0a1`. No historical migration was modified
  during final verification.

Runtime and security gates:

- The real Keycloak smoke passed: password-grant token, discovery, JWKS, signed RS256 validation,
  and issuer/subject resolution. Browser E2E is not claimed.
- The compact representative identity/security selection passed `13` tests, including local
  compatibility, changed-email durable binding, cross-issuer protection, unverified-email
  rejection, disabled-user rejection, no implicit tenant access, token negatives, and concurrent
  first-link behavior.
- Secret/logging safety passed: no private signing key or JWT-like token was found, and
  authentication logging does not include complete ID/access/refresh tokens, authorization codes,
  or client secrets. Repository credentials are DEV-only placeholders/substitution variables.

Full regression and static gates:

- The first full attempt exposed only `ENVIRONMENT` errors from plain Redis lacking `FT._LIST` and
  one `PRE_EXISTING_OTHER` stale link to archived T07; neither was an identity failure. Redis Stack
  was selected and the link was corrected. The exact command then passed: `1646 collected; 1642
  passed; 0 failed; 0 errors; 4 skipped; 80.72% coverage; 1025.64s` pytest elapsed.
- Ruff, format, and ty remain inherited `PASS` evidence because final verification changed no
  implementation files. The only verification correction was the documentation-state link.

State transition:

- T08 moves from `IN_PROGRESS / VERIFY_PENDING` to `AWAITING_ACCEPTANCE /
  EXTERNAL_ACCEPTANCE_PENDING`; explicit external acceptance is required before `PASS`.
- T09 and T10 remain `NOT_STARTED`; no later task was started.

## T08 - External Acceptance

Accepted: 2026-09-13

Acceptance Source:

Explicit user instruction in T09-IMPLEMENT: `T08 = PASS`.

State transition:

- T08 moved from `AWAITING_ACCEPTANCE` to `PASS`.
- Its plan moved from `docs/exec-plans/active/T08.md` to
  `docs/exec-plans/completed/T08.md`.
- T09 moved from `NOT_STARTED` to `IN_PROGRESS` at execution stage `IMPLEMENT`.
- T10 and T11 remain `NOT_STARTED`.

## T09-IMPLEMENT - Authorization Start

Started: 2026-09-13

Recovery evidence:

- Branch `main`, recovery HEAD `bf0d5b9`; extensive pre-existing T00-T08/M01 worktree changes are
  preserved without reset, checkout, stash, deletion, or broad commit.
- Existing authorization is reusable but fragmented: `User.role`/`is_admin` is tenant-local state,
  JWTs embed role/scope snapshots, protected routes use active-token dependencies, and most admin
  routes use a coarse application `SUPER_ADMIN` check.
- No separate tenant-membership table exists; the tenant-owned active `User` row currently acts as
  the local account and tenant membership/entitlement record.
- T08 is `PASS`; T09 is `IN_PROGRESS / IMPLEMENT`; T10 and T11 remain `NOT_STARTED`.

## T09-IMPLEMENT - Authorization Complete

Completed: 2026-09-13

Implementation:

- Consolidated application roles, capability scopes, current tenant membership resolution,
  reason-coded policy decisions, and HTTP/WebSocket route policy under `app.authorization`.
- Protected requests reload the tenant-owned local `User` membership and role from PostgreSQL;
  signed JWT role/scope fields remain compatibility snapshots, and upstream OIDC authority claims
  are ignored.
- Replaced blanket admin-route authority with the route inventory's capability requirements while
  preserving existing service-level resource checks and T07 RLS as the database defense.
- Added minimal tenant membership/role/status administration with explicit tenant predicates,
  self-change and privilege-escalation prevention, last-admin protection, and atomic audit rows.
- Added additive migration `c7d8e9f0a1b2` for forced-RLS `authorization_audit_events`; no historical
  T09 migration edit was made.

Verification:

- Targeted authorization/security/WebSocket/migration-chain tests: `53 passed`, one non-blocking
  short test-secret warning.
- Fresh-migration PostgreSQL RLS smoke: `3 passed`; an allowed application `SUPER_ADMIN` remained
  unable to read another tenant and the runtime login remained non-super/non-`BYPASSRLS`.
- Upgrade from `b6c7d8e9f0a1` to `c7d8e9f0a1b2` preserved a seeded legacy administrator and created
  the audit relation with enabled/forced RLS.
- Final inventory: 120 classified HTTP routes, 2 classified WebSocket routes, 4 classified mounts,
  and zero unclassified production routes. Alembic has one head, `c7d8e9f0a1b2`.
- Repository-wide Ruff, format check, and ty passed. The full backend pytest suite was not run, per
  IMPLEMENT-stage scope.

State transition:

- T08 remains `PASS`.
- T09 remains `IN_PROGRESS` and moves to `VERIFY_PENDING`; external verification is required.
- T10 and T11 remain `NOT_STARTED`; neither task was started.

## T09-FINAL-VERIFY - Authorization final verification

Completed: 2026-09-13

Status: `NEEDS_EVIDENCE`

Execution Stage: `VERIFY_BLOCKED`

Recovery confirmed T08 `PASS`, T09 `IN_PROGRESS / VERIFY_PENDING`, T10 `NOT_STARTED`, branch
`main`, and recovery HEAD `bf0d5b9`. The extensive pre-existing worktree was preserved; no reset,
checkout, stash, deletion, commit, or production implementation change was performed.

Preflight and authorization boundary:

- `docker compose config` passed. Isolated disposable PostgreSQL, Redis, and Qdrant services and
  the project RabbitMQ container were reachable; unrelated containers were not modified.
- Live PostgreSQL inspection confirmed `authorization_audit_events` is `TENANT_OWNED`, with
  `tenant_id`, the expected indexes and foreign keys, `ENABLE + FORCE ROW LEVEL SECURITY`, and a
  policy containing both `USING` and `WITH CHECK`. A runtime-role Tenant A query could not see or
  insert Tenant B audit data. Runtime/maintenance roles were non-superuser and non-`BYPASSRLS`.
- Fresh migration passed to `c7d8e9f0a1b2`. Upgrade from `b6c7d8e9f0a1` preserved a seeded tenant,
  user, and SUPER_ADMIN state and added the forced-RLS audit table. `alembic heads` reports one head.
- Final inventory passed with 120 HTTP routes, 2 WebSocket routes, 4 mounts, and zero unclassified
  production routes. Public-route sanity and the injected-route deny-by-default guard passed.
- Focused T09 authorization tests passed `21`; infrastructure-independent route/policy checks passed
  `4`. Runtime authorization, same-JWT revocation, OIDC/local convergence, claim non-authority,
  privilege escalation, sensitive-action separation, atomic audit, and both WebSocket policy paths
  all passed.

Full backend regression:

- Required command result: `1666 collected; 1630 passed; 24 failed; 30 errors; 4 skipped; 79.27%
  coverage; 1125.63s (18:45)`. This does not satisfy the T09 acceptance gate.
- Failure classification: `PRE_EXISTING_OTHER`.
- Root-cause grouping: 22 Qdrant failures/errors were caused by loopback proxy routing; the focused
  affected selection passed `23` tests with `NO_PROXY=127.0.0.1,localhost`. Eight Redis workflow
  errors reproduce the RedisVL restriction that RediSearch indexes cannot use test DB 15. Two
  legacy admin tests still assert `Admin privileges required`, while the current centralized
  deny-by-default policy intentionally returns `Access is not permitted`.

Static and migration integrity:

- Ruff, format, and ty remain inherited `PASS` evidence because final verification changed no
  tracked implementation files. Historical migration files were not changed by T09; the additive
  `c7d8e9f0a1b2` revision remains the sole head.

State transition:

- T08 remains `PASS`.
- T09 moves from `IN_PROGRESS / VERIFY_PENDING` to `NEEDS_EVIDENCE / VERIFY_BLOCKED`; it is not
  ready for external acceptance.
- T10 and T11 remain `NOT_STARTED`; no later task was started.

## T09-FIX-REGRESSION - Focused full-suite infrastructure / legacy assertion repair

Completed: 2026-09-13

Status: `BLOCKED`

Execution Stage: `VERIFY_PENDING`

Recovery confirmed T08 `PASS`, T09 blocked by the prior full-suite regression, T10 `NOT_STARTED`,
branch `main`, and recovery HEAD `bf0d5b9`. The extensive pre-existing worktree was preserved;
only test bootstrap/fixture behavior, two stale test assertions, and execution-memory documents
were changed for this repair.

Root-cause evidence and repairs:

- Qdrant 502s were loopback proxy routing failures. A bad loopback proxy reproduction failed, and
  the repaired test bootstrap preserved existing `NO_PROXY`/`no_proxy` values while adding
  `localhost`, `127.0.0.1`, and `::1`; the affected Qdrant group then passed `22` tests. Qdrant
  collection cleanup remained process/run scoped, and production networking was unchanged.
- RedisVL 0.16.0 / `langgraph-checkpoint-redis` 0.4.0 uses RediSearch index creation, which Redis
  rejects on DB 15 with `Cannot create index on db != 0`. The generic fixture remains on DB 15;
  only the RedisVL checkpointer uses DB 0 with UUID-scoped index/key prefixes and scoped teardown,
  without `FLUSHALL`; the RedisVL workflow group passed `7` tests and skipped one optional real-LLM
  case under dummy credentials. Post-test DB 0 indexes/keys and DB 15 state were clean.
- The two legacy admin-message assertions expected `Admin privileges required`, but the current
  centralized deny-by-default policy correctly returns status `403` with stable detail
  `Access is not permitted`. Updating those tests to the stable contract made the admin API group
  pass `15` tests; no production authorization handler or policy changed.

Focused T09 security smoke passed `4` tests, and the isolated application `SUPER_ADMIN`/RLS smoke
passed `1` test. Scoped Ruff, format check, and ty passed. The full backend coverage-gated suite was
not run in this FIX_IMPLEMENT thread; Luna must run it during final verification.

State transition:

- T08 remains `PASS`.
- T09 remains `BLOCKED / VERIFY_PENDING`; focused blockers are repaired, but full-suite regression
  and coverage evidence are pending.
- T10 and T11 remain `NOT_STARTED`; no later task was started.

## T09-FINAL-VERIFY - Final authorization regression

Completed: 2026-09-13

Status: `BLOCKED`

Execution Stage: `VERIFY_PENDING`

Recovery confirmed T08 `PASS`, T09 `BLOCKED / VERIFY_PENDING`, T10 `NOT_STARTED`, branch `main`,
and recovery HEAD `bf0d5b9`. The extensive pre-existing worktree was preserved; no production,
authorization, RLS, Qdrant, or Redis architecture file was changed.

Verification:

- Preflight passed for PostgreSQL, Redis, RabbitMQ, Qdrant, Compose syntax, canonical test
  isolation, and loopback proxy exclusion.
- Tiny smoke passed: one Qdrant regression test, one RedisVL checkpointer test, one legacy admin
  403 contract test, same-JWT role revocation, and the route inventory guard (`5 passed`).
- `uv run pytest --cov=app --cov-fail-under=75` completed in `943.73s` (`0:15:43`):
  `1666 collected; 1593 passed; 16 failed; 20 errors; 37 skipped; 79.29% coverage`.
  The Qdrant loopback proxy, RedisVL DB 15, and legacy admin-message blockers did not recur.
- Failure classifications: `ENVIRONMENT` covers 13 memory/workflow/performance failures plus 20
  context errors caused by denied `cl100k_base.tiktoken` download, and one sparse embedder failure
  caused by denied Hugging Face model download; `FIXTURE_REGRESSION` covers the collection-time
  OIDC `nbf` case, whose six-case selection passes in isolation; `PRE_EXISTING_OTHER` covers the
  unrelated zero-vector safety fallback assertion.
- Post-suite Qdrant collections were empty. RedisVL DB 0 had no indexes or checkpoint keys; DB 15
  contained only `test:`-prefixed keys and no RedisVL indexes. No `FLUSHALL` was issued. Alembic
  reports one head, `c7d8e9f0a1b2`.
- Ruff, format, and ty remain inherited `PASS` evidence. No T10 work was started.

State transition:

- T08 remains `PASS`.
- T09 remains `BLOCKED / VERIFY_PENDING`; the authorization-focused gates and repair groups pass,
  but the full backend gate is not green.
- T10 and T11 remain `NOT_STARTED`; no later task was started.

## T09-FIX-HERMETIC-SAFETY - Offline tests, OIDC time fixture, and safety fallback

Completed: 2026-09-13

Status: `BLOCKED`

Execution Stage: `VERIFY_PENDING`

- Classified the tiktoken-affected cases as unit/domain or normal integration tests and the sparse
  embedder case as an adapter conversion test. Added application-owned injection seams plus
  deterministic test providers; the affected matrix passed `37`, with one existing optional
  `requires_llm` skip and no external tokenizer/model construction.
- Rebuilt hostile OIDC claims immediately before signing from timezone-aware UTC. The future-`nbf`
  case passed alone, and the six neighboring security cases passed after unrelated tests in the same
  process; production issuer/audience/signature/subject/time validation was not changed.
- Corrected Layer 3 safety control flow so unusable reference/query vectors and provider failures use
  deterministic keyword fallback. Dangerous text remains blocked, harmless text follows the existing
  safe degraded behavior, and valid semantic evaluation remains unchanged; the combined safety/OIDC
  group passed `41` tests.
- Same-JWT role revocation, route inventory fail-closed behavior, and SUPER_ADMIN RLS independence
  passed `3` focused tests. Scoped Ruff, format, and ty passed.
- T09 remains `BLOCKED / VERIFY_PENDING` until Luna reruns the full backend coverage gate. T10 remains
  `NOT_STARTED`.

## T09-FINAL-VERIFY - Final Hermetic Full Regression

Completed: 2026-09-13

Status: `BLOCKED`

Execution Stage: `VERIFY_PENDING`

- Preflight passed for PostgreSQL, Redis, RabbitMQ, Qdrant, Compose syntax, canonical isolated
  endpoints, and loopback proxy exclusion. The six-test final smoke passed the hermetic provider
  guard, OIDC `nbf`, safety fallback, same-JWT revocation, and route inventory guard.
- The exact `uv run pytest --cov=app --cov-fail-under=75` command passed: `1673 collected; 1636
  passed; 0 failed; 0 errors; 37 skipped; 80.58% coverage; 969.37s (0:16:09)`. No new skips were
  introduced; tokenizer/model paths did not require external downloads or test-only cache warm-up.
- Qdrant cleanup passed with zero collections. RedisVL DB 0 has no remaining search index, but `144`
  raw `checkpoint_latest`/`write_keys_zset` keys remain because the installed saver fixture removes
  indexes without removing those unindexed registry keys. This is `REDISVL_TEST_INFRA`; no
  `FLUSHALL` was issued and no shared/development store was touched.
- Generic Redis stayed on the dedicated DB 15 test store; Alembic has one head at `c7d8e9f0a1b2`.
  Authorization, RLS, OIDC validation, production Redis/Qdrant networking, and safety policy were
  unchanged.

State transition:

- T08 remains `PASS`.
- T09 remains `BLOCKED / VERIFY_PENDING`; full backend regression and coverage pass, but RedisVL
  scoped cleanup evidence is not green.
- T10 remains `NOT_STARTED`; no later task was started.

## T09-FIX-REDISVL-CLEANUP - RedisVL test registry-key isolation / cleanup

Completed: 2026-09-13

Recovery confirmed T08 `PASS`, T09 `BLOCKED / VERIFY_PENDING`, T10 `NOT_STARTED`, branch `main`,
and HEAD `bf0d5b9`. The worktree contained unrelated prior enterprise-hardening changes; only the
RedisVL test fixture/helper, its regression tests, and execution-state documentation were touched
for this task.

The clean-room reproduction created one checkpoint and one pending write with unique document
prefixes. The installed `langgraph-checkpoint-redis`/RedisVL path removed indexed documents when
the indexes were dropped, but left globally named `checkpoint_latest:*` and `write_keys_zset:*`
auxiliary keys; pointer values and sorted-set members retained the run-specific prefixes. The
official thread-delete API requires complete thread ownership knowledge, so the fixture uses the
smaller scoped-cleanup strategy instead of a dedicated second Redis architecture.

Added `tests/_redisvl.py::cleanup_redisvl_resources`, which drops both run indexes, scans exact
run-prefixed document keys, deletes latest pointers only when their values reference the current
checkpoint prefix, and removes only current-run members from write registries. It never flushes a
database and preserves mixed-run registry members.

Verification:

- RedisVL/checkpointer group: `11 passed, 1 skipped` (the existing optional `requires_llm` skip).
- Cleanup ownership, DB0/DB15 sentinel protection, mixed-run ownership, and two repeated lifecycles:
  `3 passed`; clean-room DB0 and DB15 post-checks both reported zero keys.
- T09 smoke: same-JWT role revocation and route-inventory guard, `2 passed`.
- Scoped Ruff, format, and ty: `PASS`.
- No new skips, no `FLUSHALL`/`FLUSHDB`, and no shared/development Redis mutation. Authorization,
  RLS, production Redis, Celery broker, and all other production architecture remained unchanged.

State transition:

- T09 remains `BLOCKED / VERIFY_PENDING`; the focused RedisVL isolation blocker is repaired, but the
  final full backend regression and coverage gate must be rerun by the next verification stage.
- T10 remains `NOT_STARTED`; no later task was started.

## T09-FINAL-VERIFY - Final authorization + RedisVL isolation acceptance gate

Completed: 2026-09-13

Status: `AWAITING_ACCEPTANCE`

Execution Stage: `EXTERNAL_ACCEPTANCE_PENDING`

Recovery confirmed T08 `PASS`, T09 `BLOCKED / VERIFY_PENDING`, T10 `NOT_STARTED`, branch `main`,
and HEAD `bf0d5b9`. No implementation files were modified during final verification.

Verification:

- PostgreSQL, Redis, RabbitMQ, Qdrant, Compose syntax, canonical test isolation, and loopback proxy
  exclusion passed. The five-test final smoke passed RedisVL lifecycle cleanup, DB0 sentinel
  protection, same-JWT revocation, route inventory, and zero-vector safety fallback.
- The exact `uv run pytest --cov=app --cov-fail-under=75` command passed `1676` collected tests:
  `1639 passed`, `0 failed`, `0 errors`, `37 skipped`, `80.59% coverage`, `923.01s (0:15:23)`.
  The skip count matched the prior legitimate run and no regression was converted into a skip.
- After the complete suite, RedisVL DB0 had `0` indexes and `0` current-run registry resources;
  the unrelated DB0 sentinel remained. Generic DB15 preserved its sentinel, Qdrant had `0`
  collections, and no shared-store `FLUSHALL`/`FLUSHDB` was used.
- No external tokenizer/model download or test-only cache warm-up was required. Alembic reports
  one head at `c7d8e9f0a1b2`; accepted authorization, RLS, OIDC, safety, and production
  Redis/Qdrant boundaries remain unchanged. Ruff, format, and ty remain `PASS` from the focused
  repair verification.

State transition:

- T08 remains `PASS`.
- T09 is now `AWAITING_ACCEPTANCE / EXTERNAL_ACCEPTANCE_PENDING`; all final verification gates passed.
- T10 remains `NOT_STARTED`; no later task was started.

# T10-IMPLEMENT - Secure Browser Session start

Started: 2026-09-13

Status: `IN_PROGRESS`

Execution Stage: `IMPLEMENT`

- Received explicit external acceptance `T09 = PASS`; archived the accepted T09 execution plan.
- Recovery confirmed branch `main`, HEAD `bf0d5b9`, and the extensive pre-existing T00–T09/M01
  worktree changes. No unrelated change will be reset, stashed, deleted, or overwritten.
- T10 now owns browser cookie credential transport, CSRF and Origin protection, browser logout and
  revocation, OIDC cookie delivery, frontend token-storage removal, and cookie-authenticated
  WebSocket handshakes while preserving Bearer compatibility and T08/T09 boundaries.
- T10 is `IN_PROGRESS / IMPLEMENT`; T11 remains `NOT_STARTED`.

## T10-IMPLEMENT - Secure Browser Session complete

Completed: 2026-09-14

Status: `IN_PROGRESS`

Execution Stage: `VERIFY_PENDING`

Implemented one browser authentication transport over the existing application JWT: local browser
login and OIDC completion set a host-only HttpOnly cookie with production Secure, explicit
SameSite, root Path, and JWT-bounded lifetime. Bearer-only API compatibility remains on the same
principal and T09 authorization seam.

Unsafe cookie requests now require a signed random CSRF token bound to token ID, login session, and
expiry plus exact configured Origin (or exact Referer fallback). Conflicting dual transports are
rejected; matching Cookie/Bearer credentials remain subject to cookie CSRF. POST logout revokes in
the existing Redis infrastructure before clearing the cookie, and authentication rotates a valid
prior browser credential.

Browser WebSockets now authenticate from the HttpOnly cookie with exact Origin and current T09
scope/tenant authorization. Query `token`/`access_token` credentials are rejected; safe non-browser
Bearer headers remain supported. The frontend uses cookie credentials, memory-only CSRF and user
state bootstrapped from `/me`, removes only legacy `auth-storage`, calls server logout, and strips
credential parameters from WebSocket URLs. Credential fields are redacted from structured and raw
logs, and both new routes are in the T09 inventory.

Verification:

- Targeted backend security selection: `28 passed`.
- Targeted frontend Vitest: `4` files, `9 passed`; targeted Chromium: `1 passed`.
- Scoped Ruff, Ruff format, ty, ESLint, Prettier, and TypeScript checks: `PASS`.
- Static frontend credential scans: no token persistence, persisted-token Authorization, token log,
  or token-bearing WebSocket construction.
- Alembic: one head, `c7d8e9f0a1b2`; no T10 migration or historical migration edit.
- Full backend regression, full relevant frontend regression/build, final live browser/backend
  integration, and post-suite guards were intentionally deferred to Luna VERIFY.

State transition:

- T09 remains `PASS`.
- T10 remains `IN_PROGRESS` and moves to `VERIFY_PENDING`; it is not self-marked accepted.
- T11 remains `NOT_STARTED`; no later task was started.

## T10-FINAL-VERIFY - Secure Browser Session final verification

Completed: 2026-09-14

Status: `AWAITING_ACCEPTANCE`

Execution Stage: `EXTERNAL_ACCEPTANCE_PENDING`

Recovery confirmed T09 `PASS`, T10 `IN_PROGRESS / VERIFY_PENDING`, T11 `NOT_STARTED`, branch
`main`, and HEAD `bf0d5b9`. No production implementation files were changed during VERIFY.

Verification evidence:

- PostgreSQL, Redis, RabbitMQ, Qdrant, Docker Compose syntax, and Playwright runtime preflight
  passed. The focused HTTP/WebSocket security smoke passed `22` tests.
- The exact full backend command passed `1690` collected, `1686` passed, `0` failed, `0` errors,
  `4` skipped, and `80.91%` coverage in `1227.08s (0:20:27)`.
- Canonical frontend checks passed: Vitest `7` files / `17` tests, ESLint, Prettier, TypeScript,
  and production build. Focused Chromium browser E2E passed `1` test, observing HttpOnly cookie
  metadata, empty auth storage, a CSRF-protected mutation, and unauthenticated state after logout.
- Cookie configuration, CSRF/session binding, exact Origin/Referer validation, CORS credential
  safety, Bearer compatibility, ambiguous credential protection, logout and same-cookie role
  revocation, OIDC callback confidentiality, WebSocket cookie/origin/scope/revocation/query-token
  rejection, frontend transport, route inventory, and sensitive logging gates passed.
- RedisVL cleanup, generic Redis isolation, and Qdrant run-scoped cleanup checks passed. Existing
  development resources were preserved; no shared-store flush or destructive cleanup was used.
- Route inventory remains `122` classified HTTP routes and `2` classified WebSocket routes with
  `0` unclassified production routes. Alembic remains a single head at `c7d8e9f0a1b2`; no T10
  migration was added and no historical migration was modified.

State transition:

- T09 remains `PASS`.
- T10 is `AWAITING_ACCEPTANCE / EXTERNAL_ACCEPTANCE_PENDING`; all final verification gates passed.
- T11 remains `NOT_STARTED`; no later task was started.

## T11-IMPLEMENT - Compliance Lifecycle

Completed: 2026-09-14

Status: `IN_PROGRESS`

Execution Stage: `VERIFY_PENDING`

Recovery received the explicit external gate `T10 = PASS`; the accepted T10 plan is archived,
T12 remains `NOT_STARTED`, branch is `main`, and the pre-existing dirty worktree was preserved.

Implementation evidence:

- Added a canonical classification/lifecycle registry covering all SQLModel production tables and
  active tenant-scoped derived/object stores, with conservative configurable engineering defaults;
  no legal or certification claim was introduced.
- Added bounded tenant retention with dry-run, explicit timestamp predicates, batch limits,
  idempotent retries, tenant-safe local knowledge-object cleanup, maintenance-worker scheduling,
  structured failure logs/metrics, and the `RETENTION_EXECUTION_ENABLED` emergency stop.
- Added compliance audit events and PostgreSQL trigger/privilege enforcement so runtime and
  application SUPER_ADMIN identities can append but cannot UPDATE or DELETE audit evidence;
  audit retention remains explicitly indefinite.
- Added exact-operation feedback-export approvals with tenant/requester/hash binding, current
  authorization rechecks, separate approver enforcement, expiry, single-use artifact semantics,
  transactional success/failure audit evidence, and short-lived tenant-owned artifacts.
- Added additive migration `d8e9f0a1b2c3`, immediate forced-RLS protection for all new tenant tables,
  capability-scoped APIs/route inventory entries, low-cardinality Prometheus metrics, and focused
  lifecycle runbooks.

Targeted verification evidence:

- `uv run pytest tests/compliance -q --tb=short`: `20 passed`.
- Existing feedback-export regression selection: `2 passed`.
- Pure migration-chain assertions: `10 passed`.
- Real PostgreSQL runtime-role immutable-audit boundary test: `1 passed`.
- Final route inventory: `127` classified HTTP routes, `2` classified WebSocket routes, `4`
  classified mounts, and `0` unclassified production routes.
- Scoped Ruff format check, Ruff lint, and `ty check --error-on-warning`: PASS.
- `uv run alembic heads`: one head, `d8e9f0a1b2c3`.
- Full backend regression, fresh/upgrade migration verification, runtime retention integration,
  post-suite audit/approval/RLS checks, and final route inventory remain for Luna VERIFY; the full
  backend suite was intentionally not run during IMPLEMENT.

State transition:

- T10 remains externally accepted `PASS`.
- T11 remains `IN_PROGRESS` and moves to `VERIFY_PENDING`.
- T12 remains `NOT_STARTED`; no later task was started.

## T11-FINAL-VERIFY - Compliance Lifecycle final verification

Completed: 2026-09-14

Status: `NEEDS_EVIDENCE`

Execution Stage: `VERIFY_BLOCKED`

Recovery confirmed T10 `PASS`, T11 `IN_PROGRESS / VERIFY_PENDING`, T12 `NOT_STARTED`, branch
`main`, and HEAD `bf0d5b9`. No production implementation files were changed during VERIFY.

Verification evidence:

- PostgreSQL, Redis, RabbitMQ, Qdrant, and canonical M01 isolation preflight passed. Fresh migration
  and RLS integration passed `13`; the isolated upgrade from `c7d8e9f0a1b2` preserved representative
  data, reached `d8e9f0a1b2c3`, installed T11 RLS/immutability objects, and performed no retention.
- Runtime retention passed `6` focused tests, approval/export API and service flows passed `8`,
  classification/audit-redaction passed `3`, metrics/routes passed `3`, RedisVL/generic Redis
  cleanup passed `3`, and Qdrant tenant cleanup passed `4`. The registry has `51` classified
  datasets (`48` tenant-owned and `3` global/system) with zero unclassified production datasets.
- Final runtime inventory is `127` classified HTTP routes, `2` classified WebSocket routes, and
  `4` classified mounts with zero unclassified production routes; sensitive compliance routes are
  not PUBLIC. Runbooks and unsupported certification/legal-claim checks passed.
- The required full backend command collected `1712`: `1705 passed`, `3 failed`, `0 errors`,
  `4 skipped`, `80.98%` coverage, and `1543.50s (0:25:43)`. Failure classifications are
  `ROUTE_INVENTORY` (legacy test asserts 122 HTTP entries while the final inventory has 127) and
  `PRE_EXISTING_OTHER` (one timing-sensitive cache benchmark, which passed on focused rerun; the
  stale historical T10 active-plan link was synchronized to `completed/T10.md` after the run).
- Static gates remain inherited `PASS` for Ruff, format, and ty; Alembic reports the single head
  `d8e9f0a1b2c3`. No shared-store flush or broad destructive cleanup was used.

State transition:

- T10 remains externally accepted `PASS`.
- T11 moves from `IN_PROGRESS / VERIFY_PENDING` to `NEEDS_EVIDENCE / VERIFY_BLOCKED`; external
  acceptance is not requested because the required full backend gate is not green.
- T12 remains `NOT_STARTED`; no later task was started.

## T11-FIX-FINAL-REGRESSION - Route inventory, cache benchmark, and documentation repair

Completed: 2026-09-14

Status: `BLOCKED`

Execution Stage: `VERIFY_PENDING`

Context recovery confirmed T10 `PASS`, T11 `NEEDS_EVIDENCE / VERIFY_BLOCKED` before this focused
repair, T12 `NOT_STARTED`, branch `main`, and HEAD `bf0d5b9`. The pre-existing dirty worktree was
preserved and no production implementation architecture was changed.

Focused repairs and evidence:

- The legacy route test's historical `122` HTTP count was replaced with structural checks for route
  registration, policy coverage, deny-by-default guards, and protected T11 entries. The runtime
  inventory remains `127` classified HTTP routes, `2` WebSocket routes, and `0` unclassified
  production routes; the selected route/security group passed `4` tests.
- The cache benchmark now uses a serializable mocked profile, warms and clears the exact cache key,
  and compares medians across five miss/hit pairs. Five sequential focused executions passed; all
  hit medians were below miss medians (`2.26/1.12`, `2.33/1.23`, `1.87/1.01`, `2.40/1.51`, and
  `1.93/1.10` ms), proving the invariant without changing production cache behavior.
- The stale archived T10 link was synchronized to `docs/exec-plans/completed/T10.md`; the focused
  documentation/link check passed `2` tests.
- The minimal T11 security smoke passed `3` approval/retention tests plus `1` real PostgreSQL
  immutable-audit boundary test. Targeted Ruff, format, and ty checks pass, and Alembic remains the
  single head `d8e9f0a1b2c3`.

State transition:

- T10 remains externally accepted `PASS`.
- T11 moves from `NEEDS_EVIDENCE / VERIFY_BLOCKED` to `BLOCKED / VERIFY_PENDING`; the focused final
  regression blockers are repaired, but the full backend regression and post-suite verification
  remain pending.
- T12 remains `NOT_STARTED`; no later task was started.

## T11-FINAL-VERIFY - Compliance Lifecycle final regression gate

Completed: 2026-09-14

Status: `AWAITING_ACCEPTANCE`

Execution Stage: `EXTERNAL_ACCEPTANCE_PENDING`

Context recovery confirmed T10 `PASS`, T11 `BLOCKED / VERIFY_PENDING` before this gate, T12
`NOT_STARTED`, branch `main`, and HEAD `bf0d5b9`. No implementation files were changed during this
final verification.

Verification evidence:

- PostgreSQL, authenticated Redis, RabbitMQ management, and Qdrant readiness preflight passed. The
  repository's generic Redis DB 15, scoped RedisVL DB 0, and run-scoped Qdrant collection isolation
  configuration remained active.
- Final smoke passed `7` focused tests plus `1` real PostgreSQL immutable-audit test. Runtime route
  inventory is `127` classified HTTP routes, `2` classified WebSocket routes, and `0` unclassified
  production routes; sensitive T11 routes remain protected and non-PUBLIC.
- `uv run pytest --cov=app --cov-fail-under=75` passed: `1712` collected, `1708 passed`, `0 failed`,
  `0 errors`, `4 skipped`, `80.98%` coverage, and `1488.90s (0:24:48)`. No new skip, xfail, or
  external-only suppression was introduced.
- Post-suite isolation passed `8` focused tests covering RedisVL cleanup, generic tenant/system Redis
  preservation, and Qdrant run-scoped cleanup. Existing T11 object lifecycle cleanup evidence remains
  passing; no residual test artifact was reported.
- `uv run alembic heads` reports the single head `d8e9f0a1b2c3`; targeted Ruff, format, and ty remain
  PASS. No T11 security/compliance regression or unsupported certification claim was found.

State transition:

- T10 remains externally accepted `PASS`.
- T11 moves from `BLOCKED / VERIFY_PENDING` to `AWAITING_ACCEPTANCE / EXTERNAL_ACCEPTANCE_PENDING`;
  external acceptance is required and T11 is not marked `PASS`.
- T12 remains `NOT_STARTED`; no later task was started.

## T12-IMPLEMENT - Durable Conversation Runtime start

Started: 2026-09-14

Status: `IN_PROGRESS`

Execution Stage: `IMPLEMENT`

- Received explicit external acceptance `T11 = PASS`; archived the accepted T11 execution plan.
- Recovery confirmed branch `main`, HEAD `bf0d5b9`, and extensive pre-existing T00-T11/M01
  worktree changes. No unrelated change will be reset, stashed, deleted, overwritten, or broadly
  committed.
- T12 owns the durable conversation/turn/run lifecycle, idempotency, per-conversation concurrency,
  cancellation, stale-result acceptance, runtime events/recovery, and the LangGraph executor seam.
- T12 is `IN_PROGRESS / IMPLEMENT`; T13 remains `NOT_STARTED`.

## T12-IMPLEMENT - Durable Conversation Runtime implementation

Completed: 2026-09-14

Status: `IN_PROGRESS`

Execution Stage: `VERIFY_PENDING`

Implemented the PostgreSQL-authoritative conversation execution boundary without replacing the
existing intent, multi-intent, LangGraph, agent, tool, RAG, memory, safety, review, feedback, or
evaluation application. The canonical runtime now owns conversation/turn/run identity, centralized
transitions, tenant-and-conversation-scoped idempotency, transaction-scoped concurrency control,
logical cancellation, optimistic async-result acceptance, one terminal assistant message, ordered
durable lifecycle events, replay/final-result recovery, and bounded orphan reconciliation.

The HTTP chat adapter depends on `ConversationRuntime`; LangGraph event and checkpoint details are
isolated in `LangGraphConversationExecutor`. Three authenticated tenant-scoped runtime routes expose
durable status/final result, event replay after sequence, and idempotent logical cancellation.
Migration `e9f0a1b2c3d4` adds five tenant-owned tables with immediate forced RLS, extends the existing
message model instead of creating a parallel message framework, and adds T07/T11 inventory entries.

Verification evidence:

- Conversation runtime group: `36 passed`.
- Existing chat API and runtime reconnect/control integration: `13 passed`.
- Representative graph compile, parallel scheduler, intent, multi-intent, memory, and existing
  review compatibility: `12 passed`.
- Fresh full-chain migration forced-RLS catalog and direct conversation-table isolation: `2 passed`.
- Alembic revision-graph regression, including the exact T11-to-T12 link: `11 passed`.
- Classification and route-inventory guards: `3 passed`; `126` application HTTP policies plus `4`
  framework HTTP routes (`130` registered HTTP total) and `2` WebSocket policies, with zero
  unclassified production routes.
- Scoped Ruff, Ruff format, and ty with `--error-on-warning`: PASS; `git diff --check`: PASS;
  `uv run alembic heads`: one head, `e9f0a1b2c3d4`.

No complete backend suite, provider fallback/model gateway, AI retry/failure policy, frontend
transport redesign, Kafka, Temporal, or later roadmap work was run or implemented. T12 remains
`IN_PROGRESS / VERIFY_PENDING`; T13 remains `NOT_STARTED`.

## T12-FINAL-VERIFY - Durable Conversation Runtime final verification

Completed: 2026-09-14

Status: `NEEDS_EVIDENCE`

Execution Stage: `VERIFY_BLOCKED`

Recovery confirmed T11 `PASS`, T12 `IN_PROGRESS / VERIFY_PENDING`, T13 `NOT_STARTED`, branch
`main`, HEAD `bf0d5b9`, and the extensive pre-existing dirty worktree; no unrelated change was
reset, stashed, deleted, overwritten, or committed.

Verification evidence:

- PostgreSQL, Redis Stack, RabbitMQ, and Qdrant preflight passed. A dedicated `test_t12_verify`
  RabbitMQ vhost with scoped permissions was created for isolation; existing test runs retained the
  memory-broker convention rather than rerunning the T04 matrix.
- Route diff passed: T11's accepted `127` HTTP routes are the current registered set minus the four
  framework routes and the three additive T12 runtime routes. No T11/T10 route was removed, both
  WebSockets remain, sensitive routes remain non-PUBLIC, and unclassified production routes are `0`.
- Fresh migration passed through `e9f0a1b2c3d4`. Upgrade from seeded `d8e9f0a1b2c3` preserved tenant,
  user, message, and T11 compliance records, installed the five runtime tables with forced RLS and
  `USING`/`WITH CHECK`, and created no runtime rows during migration.
- Pre-suite runtime/security smoke passed `39`; post-suite logical guards passed `5`; post-suite
  RedisVL/generic Redis/Qdrant isolation passed `14`; migration-chain assertions passed `11`.
- The required `uv run pytest --cov=app --cov-fail-under=75` collected `1747` tests and finished with
  `1746 passed`, `1 failed`, `0 errors`, `4 skipped`, `81.61%` coverage, and `1987.61s (0:33:07)`.
  The sole failure is `tests/performance/test_performance.py::test_chat_endpoint_p95_under_500ms`:
  mocked authenticated `user_id=999` has no `users` row, so `conversations_user_id_fkey` rejects
  durable turn setup. Classification: `BACKEND_REGRESSION`; minimum focused FIX is to make that
  fixture create/use a durable user before rerunning the full gate.
- Post-suite guards remained green; Ruff, format, and ty remain inherited PASS; no production code
  changed during VERIFY. Human-review N/A is justified by the absence of graph `interrupt()`;
  outbox N/A is justified because T12 adds no new broker dispatch transaction.

State transition:

- T11 remains externally accepted `PASS`.
- T12 moves from `IN_PROGRESS / VERIFY_PENDING` to `NEEDS_EVIDENCE / VERIFY_BLOCKED`; external
  acceptance is not requested until the focused compatibility fix and clean full regression.
- T13 remains `NOT_STARTED`; no later task was started.

## T12-FIX-PERFORMANCE-USER-FIXTURE - Repair stale authenticated benchmark user

Completed: 2026-09-14

Status: `BLOCKED`

Execution Stage: `VERIFY_PENDING`

- Reproduced the sole T12 full-regression failure in
  `tests/performance/test_performance.py::test_chat_endpoint_p95_under_500ms`: the mocked
  principal used `user_id=999` without a durable `users` row, and PostgreSQL correctly rejected
  conversation creation at `conversations_user_id_fkey`.
- Added only a test fixture using the canonical `User` model and `async_session_maker` under the
  active `tenant_context`; the fixture commits a tenant-local user before timing and injects its
  generated ID into the authenticated principal. No production FK, runtime, authorization, or RLS
  behavior changed.
- The focused benchmark passed `5/5` sequential executions with P95 values `210.94`, `224.64`,
  `223.87`, `228.09`, and `232.32` ms. The complete `tests/performance/test_performance.py` module
  passed `4/4`; authenticated chat persistence, duplicate submission idempotency, and cross-tenant
  runtime denial smoke tests passed `3/3`; Ruff, format, and ty passed for the changed file.
- The full backend regression was intentionally not rerun in this FIX thread. T12 therefore remains
  `BLOCKED / VERIFY_PENDING` until the final verification owner reruns that gate; T13 remains
  `NOT_STARTED`.

## T12-FINAL-VERIFY - Durable Conversation Runtime final regression gate

Completed: 2026-09-14

Status: `BLOCKED`

Execution Stage: `VERIFY_PENDING`

Recovery confirmed T11 `PASS`, T12 `BLOCKED / VERIFY_PENDING`, T13 `NOT_STARTED`, branch `main`,
and HEAD `bf0d5b9`; the pre-existing dirty worktree was preserved and no production implementation
was changed.

Verification evidence:

- PostgreSQL, Redis, RabbitMQ, and Qdrant preflight passed. Final smoke passed the performance
  module (`4/4`, chat P95 `261.67` ms), duplicate submission, same-conversation concurrency,
  cancelled/stale-result rejection, cross-tenant runtime denial, and route inventory.
- The required `uv run pytest --cov=app --cov-fail-under=75` collected `1751` tests and finished
  with `1716 passed`, `13 failed`, `18 errors`, `4 skipped`, `81.28%` coverage, and `1882.19s
  (0:31:22)`. The performance benchmark passed; all `13` failures were real-LLM connection
  failures and all `18` setup errors were Windows pytest `tmp_path` permission failures.
  Classification: `ENVIRONMENT`.
- Post-suite guards passed: duplicate submission, cancelled late-result rejection, stale-result
  rejection, and route inventory. RedisVL/generic Redis cleanup passed `3/3`; Qdrant cleanup left
  zero test-scoped collections; RabbitMQ remained isolated on `test_t12_verify`.
- Route inventory is `130` registered HTTP routes (`126` application plus `4` framework), `2`
  WebSocket routes, and `0` unclassified production routes. Alembic remains one head,
  `e9f0a1b2c3d4`; historical migrations were not modified. Existing Ruff, format, and ty evidence
  remains PASS.

State transition:

- T11 remains externally accepted `PASS`.
- T12 remains `BLOCKED / VERIFY_PENDING` because the full backend acceptance gate requires zero
  failures and errors; the environment must be corrected before rerunning it. T13 remains
  `NOT_STARTED`; no later task was started.

## T12-VERIFY-ENVIRONMENT - Resolve verification environment blockers

Completed: 2026-09-14

Status: `AWAITING_ACCEPTANCE`

Execution Stage: `EXTERNAL_ACCEPTANCE_PENDING`

Recovery confirmed T11 `PASS`, T12 `BLOCKED / VERIFY_PENDING`, T13 `NOT_STARTED`, branch `main`,
and HEAD `bf0d5b9`; no production implementation was changed.

Verification evidence:

- All 13 prior LLM failures are explicitly marked `requires_llm` and use the existing `real_llm`
  fixture. The canonical dummy-key policy skipped the complete pre-existing set of `33` real-
  provider nodes with `0` failures/errors; no new skip/xfail or test-code change was introduced,
  and no public LLM request occurred. The prior attempts were caused by non-dummy provider keys
  loaded from the developer `.env`, not by T12 runtime behavior.
- A unique current-user temporary root passed create/write/rename/delete/child-directory preflight;
  all `18` previously errored Windows `tmp_path` tests passed under `--basetemp`, confirming a
  runner temp-permission issue without a tracked fixture or production change.
- Compact T12 smoke passed `11` tests. The chat benchmark passed with mean `195.73` ms, P95
  `236.11` ms, and P99 `273.69` ms.
- The final hermetic `uv run pytest --basetemp=<unique-root> --cov=app --cov-fail-under=75`
  collected `1751` tests: `1714 passed`, `0 failed`, `0 errors`, `37 skipped`, `81.43%` coverage,
  elapsed `1652.38s (0:27:32)`. The `37` skips are the existing `33` real-provider marker tests
  plus `3` RabbitMQ and `1` Keycloak optional integrations; their existing skip reasons were
  confirmed and no new suppression was added.
- Post-suite duplicate/cancellation/stale/route guards passed. RedisVL/generic Redis cleanup
  passed `3/3`, Qdrant cleanup left zero test-scoped collections, RabbitMQ remained on the dedicated
  `test_t12_verify` vhost, verification temp roots were cleaned, and `alembic heads` reports the
  single head `e9f0a1b2c3d4`. Historical migrations were not modified; Ruff, format, and ty remain
  PASS.

State transition:

- T11 remains externally accepted `PASS`.
- T12 moves from `BLOCKED / VERIFY_PENDING` to `AWAITING_ACCEPTANCE /
  EXTERNAL_ACCEPTANCE_PENDING`; external acceptance is required and T12 is not marked `PASS`.
- T13 remains `NOT_STARTED`; no later task was started.

## T13-IMPLEMENT - Dynamic Model Gateway start

Started: 2026-09-14

Status: `IN_PROGRESS`

Execution Stage: `IMPLEMENT`

- Received explicit external acceptance `T12 = PASS`; archived the accepted T12 execution plan.
- Recovery confirmed branch `main`, HEAD `bf0d5b9`, and extensive pre-existing T00-T12/M01
  worktree changes. No unrelated change will be reset, stashed, deleted, overwritten, or broadly
  committed.
- T13 owns the provider-neutral model gateway, explicit candidate resolution, capability registry,
  OpenAI/DashScope/Mock adapters, normalized responses/streaming/errors, configuration, production
  remote-model migration, and hermetic real-provider test opt-in.
- Retry, automatic fallback, circuits, degraded answers, and failure budgets remain exclusively T14;
  T13 is `IN_PROGRESS / IMPLEMENT` and T14 remains `NOT_STARTED`.

## T13-IMPLEMENT - Dynamic Model Gateway implementation complete

Completed: 2026-09-14

Status: `IN_PROGRESS`

Execution Stage: `VERIFY_PENDING`

- Inventoried 22 pre-change production remote-chat construction/invocation paths. Migrated all 21
  retained paths to the canonical gateway seam and removed the startup public-provider warm-up;
  local FastEmbed/BM25 and existing modality-specific embedding/reranking ports remain out of scope.
- Added configuration-driven routes with ordered OpenAI primary and DashScope alternate candidates,
  provider-neutral request/response/stream/tool/usage contracts, capability checks before I/O, a
  narrow provider port, real async adapters, and a deterministic Mock adapter.
- Real adapters validate trusted HTTP(S) base URLs, use explicit bounded timeouts, set SDK retries to
  zero, normalize safe errors, preserve cancellation, and make exactly one selected-provider attempt.
  T13 contains no retry, automatic fallback, circuit, degradation, or provider-health policy.
- Strengthened the existing `requires_llm`/`real_llm` mechanism with explicit
  `RUN_REAL_LLM_TESTS=1` opt-in. Valid-looking credentials without opt-in skip before provider I/O;
  normal gateway correctness uses Mock or fake HTTP transports and requires no public internet.
- Targeted gateway, adapter, hermeticity, structural, and representative AI compatibility tests pass
  (`44 passed`). Evaluation/shadow route compatibility passes (`6 passed`, one unrelated
  database-bound Celery wrapper intentionally deselected). The actual marker-policy smoke skips one
  real-provider node without opt-in and makes no public request.
- The deterministic authenticated tenant flow through ConversationRuntime -> LangGraph ->
  ModelGateway -> Mock passes against a dedicated migrated PostgreSQL database. It persists one
  terminal assistant answer with `mock/mock-runtime-v1` identity and ordered runtime events; a
  cancellation race preserves `CANCELLED`, rejects the late result, and performs one provider attempt.
- Route inventory remains `130` HTTP and `2` WebSocket routes with `0` unclassified production
  routes. Ruff, Ruff format check, ty with `--error-on-warning`, project identity, `git diff --check`,
  and the single Alembic head `e9f0a1b2c3d4` pass. No migration or user-facing route was added.

State transition:

- T12 remains externally accepted `PASS`.
- T13 remains `IN_PROGRESS` and moves from `IMPLEMENT` to `VERIFY_PENDING` for independent Luna
  verification; it is not marked `PASS` or `AWAITING_ACCEPTANCE`.
- T14 remains `NOT_STARTED`; no T14 failure policy was implemented.

## T13-VERIFY - Dynamic Model Gateway final verification

Completed: 2026-09-14

Status: `AWAITING_ACCEPTANCE`

Execution Stage: `EXTERNAL_ACCEPTANCE_PENDING`

- Recovery confirmed T12 `PASS`, T13 `IN_PROGRESS / VERIFY_PENDING`, T14 `NOT_STARTED`, branch
  `main`, and HEAD `bf0d5b9`; the extensive pre-existing dirty worktree was preserved. No
  production implementation was changed during VERIFY.
- Infrastructure preflight passed for PostgreSQL, Redis, RabbitMQ, and Qdrant. A unique
  current-user-writable Windows basetemp passed create/write/rename/delete/child-directory checks.
- Focused gateway/adapter verification passed (`41 passed`); the post-suite route-resolution,
  no-fallback, direct-SDK, and hermetic-policy guards passed (`14 passed`). The deterministic T12
  ConversationRuntime -> LangGraph -> ModelGateway -> Mock completion and cancellation/stale-result
  smoke passed both before and after the full suite.
- The hermetic full command completed with exit code `0`: `1792 collected`, `1755 passed`, `0 failed`,
  `0 errors`, `37 skipped`, `81.68%` coverage, `1909.49s (31:49)`. Skip accounting remains the
  existing `33` `requires_llm`, `3` RabbitMQ, and `1` Keycloak optional cases. No new skip/xfail,
  external-only workaround, or real-provider execution was introduced.
- The real-provider fixture smoke with valid-looking keys and opt-in disabled skipped cleanly; the
  full-run audit found no OpenAI or DashScope endpoint references or provider key material in output.
  Model endpoints were loopback-only and provider keys were dummy process-local values, so no
  unexpected public request occurred. Optional real-provider smoke was not run.
- Post-suite Qdrant test-scoped collection count was `0`; Redis probes returned `PONG`; RabbitMQ
  diagnostics ping succeeded. Existing RedisVL/generic Redis cleanup and RabbitMQ memory-broker
  isolation tests passed or retained their established optional skips. Verification basetemp roots
  were removed; the full pytest log remains only in the OS temp directory.
- Route inventory remains `130` classified HTTP routes, `2` classified WebSocket routes, and `0`
  unclassified production routes. No provider/config route is PUBLIC. `e9f0a1b2c3d4` remains the
  single Alembic head; no migration or historical migration change was made by T13.
- Ruff, Ruff format, ty with `--error-on-warning`, project identity, and `uv lock --check` pass.

State transition:

- T12 remains externally accepted `PASS`.
- T13 moves from `IN_PROGRESS / VERIFY_PENDING` to `AWAITING_ACCEPTANCE /
  EXTERNAL_ACCEPTANCE_PENDING`; it is not marked `PASS`.
- T14 remains `NOT_STARTED`; no retry, automatic fallback, circuit breaker, or degraded-answer
  policy was implemented.

## M02-FIX-CI - Repair required checks for protected-main consolidation

Started: 2026-09-14

Status: `IN_PROGRESS`

Execution Stage: `PR_FIX_CI`

- Recovery confirmed PR #6's linear head `727af4bd498e`, unchanged `origin/main` `bf0d5b9`, clean
  worktree, and preserved local backup tag/external bundle. No branch cleanup or protection change
  is authorized before a successful merge.
- The first PR run passed `Brand & docs` and `Frontend`; `Backend quality` failed at `ty` on
  optional `tiktoken` imports in `app/agents/base.py`, `app/context/token_budget.py`, and
  `app/graph/subgraphs.py`. `Docker smoke` failed during API startup with Qdrant `401` because
  the workflow removed the example Qdrant key even though Compose enabled server auth. `Backend
  tests` was inspected and remained in progress; no unrelated failure was treated as in scope.
- The focused fix keeps `tiktoken` optional, centralizes its importlib boundary and fallback, and
  adds provider-available/package-missing regression coverage. The smoke workflow now supplies a
  deterministic non-production Qdrant key consistently to server and API. No production
  architecture, migration, dependency upgrade, or T14 implementation changed.

## M02 - Git main consolidation and protected-branch stop

Completed: 2026-09-14

Status: `BLOCKED`

Execution Stage: `PR_REQUIRED`

- Recovery confirmed local `main == origin/main == bf0d5b9`, one local branch, seven non-main
  remote branches, and an extensive coherent uncommitted T00-T13/M01 implementation line. Ignored
  `.env`, generated caches, coverage, uploads, dependencies, and build output were preserved and
  excluded. No high-confidence real secret was found in commit-eligible content.
- Branch inventory proved three historical feature/fix branches fully contained in `main`; three
  Dependabot tips were isolated dependency upgrades explicitly rejected as outside this no-upgrade
  maintenance scope; `origin/fix/alertmanager-config` contained one legitimate unique fix.
- Created local recovery tag `repo-consolidation-backup-20260914-201849` at
  `65a30ae5cd394e6672fb802378eadf7568f52109` through an alternate index, plus verified OS-temp
  bundle `star-warehouse-pre-consolidation-20260914-201849.bundle` containing all current refs.
- Committed the accepted project line as `620b82f` and merged the unique Alertmanager fix normally
  and without conflict as `c77987b`. README now reflects the actual Conversation Runtime, Model
  Gateway, OpenAI/DashScope/Mock adapters, tenant/RLS/security/compliance boundaries, current
  commands, hermetic test policy, T13 `PASS`, and T14 `NOT_STARTED`.
- Verification passed: identity/local links, Compose application/monitoring parses, Alertmanager
  `amtool`, Ruff, Ruff format, ty, lock check, Alembic head, diff hygiene, and 32 focused gateway
  tests after a single cold-start fake-transport timeout passed both exact and full reruns.
- The immediate pre-push fetch confirmed `origin/main` remained `bf0d5b9fe756`. GitHub rejected the
  normal push with GH006 because main requires a pull request, five required checks, and no merge
  commits. No force push or protection bypass was attempted.
- STOP condition `MAIN_BRANCH_PROTECTION_REQUIRES_PR` applies. No remote/local branch deletion or
  remote cleanup was performed. Continue with a new linear PR branch rooted at the Alertmanager
  commit, then verify the merged remote main before cleanup.

State transition:

- T13 is externally accepted `PASS`; T14 remains `NOT_STARTED`.
- M02 moves from `IN_PROGRESS` to `BLOCKED / PR_REQUIRED`.

## M02-FIX - Resume consolidation through a linear protected-main PR

Started: 2026-09-14

Status: `IN_PROGRESS`

Execution Stage: `PR_FIX`

- Recovery confirmed a clean worktree, local canonical `main` at `c5a4a1aa8be5e7e3ea2849507fef1d7c3d56d928`,
  unchanged `origin/main` at `bf0d5b9fe756fb1527c605120b03a0d6531471cd`, and the expected
  backup tag. The existing external bundle remains present and untouched.
- The rejected local range contains exactly one merge commit, `c77987b`; no missing project
  content explains the protection failure.
- `b9f1a91` is a direct linear child of `origin/main`. Constructed `repo-consolidation-pr` with one
  new normal commit, `02a91d4`, whose parent is `b9f1a91` and whose tree is the exact canonical
  `c5a4a1a` tree (`b3a03fd2e7cd3e0a250ea9f7ff6e054e2a6808f8`).
- Pre-documentation equivalence passed with zero diff, zero merge commits, and a successful
  `origin/main` ancestor check. T13 remains `PASS`; T14 remains `NOT_STARTED`.

## T14-IMPLEMENT - AI Failure Policy implementation

Started: 2026-09-15

Status: `IN_PROGRESS`

Execution Stage: `VERIFY_PENDING`

- Recovery confirmed externally accepted T13, synchronized clean `main`, and the current
  `origin/main`/local base `1b76ab2e2e3fa2afc81155fd529b38251c36ef50`. Work is isolated on the new
  `feat/t14-ai-failure-policy` branch; no main merge, T15 work, or destructive Git operation was
  performed.
- Added the provider-neutral `ModelFailurePolicy` seam. It owns finite per-candidate and total
  attempt budgets, a total deadline, injectable bounded exponential backoff/jitter and clamped
  `Retry-After`, ordered fallback, cancellation-safe streaming, safe-static degradation, and
  provider/model-scoped circuit state. Factory-created clients use Redis system keys with bounded
  half-open probes; tests inject the in-memory store. Redis outages fail open only for the breaker,
  never for local retry/deadline limits.
- Kept T13 boundaries intact: adapters still perform one provider attempt with SDK retries off,
  `ModelGateway` still invokes one explicit candidate with no automatic fallback, and T14 imports
  no provider SDK exception types. A numeric `Retry-After` hint is preserved in normalized errors
  for the policy to clamp.
- Streaming switches candidates only before a visible text/tool delta; after visible output the
  normalized failure terminates the current stream. Tool/structured-output requests cannot receive
  an arbitrary static degraded answer. Non-operational/security/capability errors do not retry,
  fallback, or trip the circuit by default.
- Added focused regression coverage for retry/fallback/deadline/cancellation, jitter and
  `Retry-After`, capability filtering, streaming no-duplication, circuit closed/open/half-open
  transitions and probe concurrency, safe degradation, configuration-error propagation, and the
  LangChain factory seam. Focused T14 tests pass (`23 passed`); the existing provider-neutral
  Model Gateway selection passes (`66 passed`) with external LangSmith tracing disabled.
- Ruff, format, ty, project identity, `uv lock --check`, and Alembic single-head checks pass;
  `e9f0a1b2c3d4` remains the sole head. Full backend regression and CI/PR verification are
  intentionally pending for VERIFY. No schema migration, dependency upgrade, public-provider
  call, or real secret was added.

State transition:

- T13 remains externally accepted `PASS`.
- T14 moves from `NOT_STARTED` to `IN_PROGRESS / VERIFY_PENDING`; external acceptance is required
  before `PASS`.
- T15 remains `NOT_STARTED`.


## T14-VERIFY-CLOSEOUT - Final regression evidence and baseline debt record

Completed: 2026-09-15

Status: `AWAITING_ACCEPTANCE`

Execution Stage: `EXTERNAL_ACCEPTANCE_PENDING`

- Preflight confirmed clean `feat/t14-ai-failure-policy` at
  `2dfcd757de851de16dc053e07c3feac26a4ad984`, synchronized with its remote, with no
  implementation changes.
- The clean-checkout backend suite ran to completion without `-x`/`--maxfail`: `1819 collected`,
  `1780 passed`, `2 failed`, `0 errors`, `37 skipped`, `81.62%` coverage, `1776.35s (29:36)`.
- Failures are `tests/model_gateway/test_openai_adapter.py::test_openai_normalized_request_and_response`
  (cold OpenAI SDK/platform initialization exceeded the existing two-second test deadline) and
  `tests/tasks/test_celery_startup.py::test_celery_app_scheduled_tasks_are_registered` (fresh
  process Celery import exceeded the existing 30-second deadline). Both reproduced in the same
  clean Linux environment from protected `main`; they are `PRE_EXISTING_BASELINE_TEST_DEBT`, not
  T14 regressions. No timeout, production code, test, or T14 implementation was changed.
- All nine focused guards passed: bounded retry, OpenAI-to-DashScope fallback, BAD_REQUEST
  no-fallback, post-visible-delta no-fallback, shared Redis OPEN state, bounded HALF_OPEN probes,
  T12 cancellation/stale-run rejection, and the T13 gateway no-fallback boundary.
- Isolation evidence passed: RedisVL/database safety (`10 passed`), no RedisVL/generic/circuit
  keys remained in the isolated Redis databases, and Qdrant collection listing was empty.
  RabbitMQ stayed on the documented `memory://` policy. No unexpected OpenAI/DashScope network,
  real credentials, new skip/xfail, or TLS-disable workaround was introduced.

State transition:

- T13 remains externally accepted `PASS`.
- T14 moves from `IN_PROGRESS / VERIFY_PENDING` to `AWAITING_ACCEPTANCE /
  EXTERNAL_ACCEPTANCE_PENDING`; external acceptance is required before `PASS`.
- T15 remains `NOT_STARTED`.

## T14-T21-INTEGRATION - Solo workflow and branch transition

Completed: 2026-09-15

Status: `PASS_WITH_NOTES`

Execution Stage: `EXTERNAL_ACCEPTANCE_COMPLETE`

- Recovery preflight confirmed the required clean branch `feat/t14-ai-failure-policy` at accepted
  HEAD `3c9c10bc25d7e77e5b53fccd36912a5150f2357b`; `git fetch origin --prune` completed.
- T14-specific verification was externally accepted as `PASS_WITH_NOTES`; feature-only regressions
  are `0`. The OpenAI SDK cold-start and Celery fresh-process import deadline sensitivities remain
  `DEFERRED_BASELINE_TEST_DEBT`, are not resolved, and do not block T15.
- The state, roadmap, root agent guidance, README status, execution-plan lifecycle reference, and
  archived T14 plan record the T14-T21 solo-development workflow. T15 was not implemented.
- Commit `8b0a48bab54d7423a51833a37f8f6ca1cee45e4d` contains only documentation/workflow/state
  changes and archives `docs/exec-plans/active/T14.md` as `docs/exec-plans/completed/T14.md`.
- The local branch was renamed to `feat/t14-t21-enterprise-hardening`.
- A normal push with upstream configuration created
  `origin/feat/t14-t21-enterprise-hardening`; `git ls-remote` verified it at the exact commit
  above. No force push was used.
- The old remote `feat/t14-ai-failure-policy` was deleted normally only after that verification.
- No application code or tests changed. No backend tests were run because the transition scope did
  not require them; `main` was not modified.

State transition:

- T13 remains externally accepted `PASS`.
- T14 moves from `AWAITING_ACCEPTANCE / EXTERNAL_ACCEPTANCE_PENDING` to externally accepted
  `PASS_WITH_NOTES`.
- T15 remains `NOT_STARTED` and is ready for the next IMPLEMENT stage on the integration branch.

## T15-IMPLEMENT-START - Frontend transport hardening

Completed: 2026-09-15

Status: `IN_PROGRESS`

Execution Stage: `IMPLEMENT`

- Recovery confirmed T14 `PASS_WITH_NOTES`, T15 `NOT_STARTED`, T16 `NOT_STARTED`, and the clean
  `feat/t14-t21-enterprise-hardening` branch at `e0563e13dbe189d7ee4cdc937aad313cf8d5ad96`.
- Required T10 browser-session, T12 conversation-runtime, T13 model-gateway, and T14 failure-policy
  contracts were read before editing. The accepted cookie/CSRF/Origin/WebSocket/OIDC boundary is
  preserved; no backend security weakening is permitted.
- Frontend inventory found one existing generic HTTP client (`apiFetch`), one SSE path (`useChat`),
  one WebSocket hook (`useWebSocket`), server-authoritative Zustand auth state, and no Axios,
  EventSource, browser Bearer header, token storage, or token-bearing WebSocket URL path.
- The existing raw Web Vitals keepalive request is classified as a legitimate non-authenticated
  telemetry exception. Existing domain hooks already route through `apiFetch`.
- `/chat` already accepts `Idempotency-Key`; T12 already exposes durable logical cancellation.
  T15 will supply/reuse a domain key for one chat submission and will not invent keys for unrelated
  mutations. Backend correlation IDs remain server-owned, with safe response metadata capture.
- The two known protected-main baseline debts (OpenAI SDK cold-start and Celery fresh-process
  import deadlines) remain deferred and are not a T15 blocker.

State transition:

- T14 remains externally accepted `PASS_WITH_NOTES`.
- T15 moves from `NOT_STARTED` to `IN_PROGRESS / IMPLEMENT`.
- T16 remains `NOT_STARTED`; no later task was started.

## T15-IMPLEMENT-CLOSEOUT - Frontend transport hardening

Completed: 2026-09-15

Status: `IN_PROGRESS`

Execution Stage: `VERIFY_PENDING`

- Implemented the canonical browser transport boundary on
  `feat/t14-t21-enterprise-hardening`: cookie-session HTTP with centralized session-bound CSRF,
  normalized/sanitized transport errors, explicit timeout/abort, bounded safe-read retry,
  idempotency-aware mutation policy, and safe correlation metadata handling.
- Replaced the customer manual stream reader with the shared SSE reader and a one-logical-run
  terminal state machine. `TURN_ACCEPTED`, deltas, metadata, terminal success/failure/cancel,
  caller abort, and T12 logical cancellation are covered; T14 provider fallback remains a backend
  concern and does not create a second frontend request.
- Hardened the reusable browser WebSocket client for cookie/session + Origin authentication,
  token-query stripping, secure scheme upgrade, bounded reconnect/backoff/jitter, and explicit
  authentication/logout close handling. No backend replay/dedup contract was invented.
- TanStack Query retries are disabled to avoid double retry. Domain hooks, multipart uploads, and
  authenticated exports continue through the canonical client. Web Vitals keepalive remains the
  only raw fetch exception and is unauthenticated telemetry.
- Frontend format check, lint, typecheck/build, full frontend unit tests (`10` files, `47` tests),
  and targeted Playwright flows (`2 passed`) passed. Focused T10 browser-session/WebSocket guards
  passed (`22 passed`), focused OIDC token-free browser tests passed (`3 passed`), the production
  route-inventory guard passed, and `uv run alembic heads` reports the single accepted head
  `e9f0a1b2c3d4`.
- The initial T10 smoke was blocked by unavailable Compose host resolution; starting only the
  required local dependencies and using explicit IPv4 loopback for the isolated test database
  allowed the same focused guards to pass. This was environment triage only. The full backend
  suite was not run.
- No backend application code, migration, database schema, or T16 work changed. The two known
  protected-main baseline debts (OpenAI SDK cold-start and Celery fresh-process import deadlines)
  remain deferred and do not block T15.

State transition:

- T14 remains externally accepted `PASS_WITH_NOTES`.
- T15 remains `IN_PROGRESS / VERIFY_PENDING`; external acceptance is required before PASS.
- T16 remains `NOT_STARTED`.

## T15-VERIFY-CLOSEOUT - Frontend transport final verification

Completed: 2026-09-15

Status: `AWAITING_ACCEPTANCE`

Execution Stage: `EXTERNAL_ACCEPTANCE_PENDING`

Branch and preflight:

- Verification ran on `feat/t14-t21-enterprise-hardening` from implementation head
  `93fde48077a998619ddce3c6c67b26abcde71f72`. `origin/feat/t14-t21-enterprise-hardening`
  matched exactly after fetch, the old branch ref was absent, and the working tree was clean.
- The production transport inventory remains one canonical HTTP client (`apiFetch`), one shared
  SSE reader/customer stream, and one reusable cookie/origin WebSocket client. The only raw fetch
  exception is unauthenticated Web Vitals telemetry; backend-owned OIDC redirects remain the
  only credential-like URL exception.

Verification:

- Frontend format check, lint, TypeScript/build, and Vitest passed: `10` files, `47` passed,
  `0` failed, `0` skipped. Focused Chromium Playwright flows passed: `2` tests.
- Focused T10 compatibility passed `26` tests, covering cookie auth, CSRF, Origin,
  logout/revocation, conflicting credentials, OIDC token-free callback behavior, WebSocket
  query-token rejection, and the HTTP/WS route inventory. Focused T12/T14 compatibility passed
  `7` tests covering logical cancellation, terminal uniqueness, fallback before visible output,
  no fallback after visible output, and one normalized terminal failure.
- HTTP, CSRF, auth-state, normalized-error, timeout, abort, bounded safe-read retry, mutation
  retry/idempotency, streaming terminal, WebSocket reconnect, storage/URL security, and TanStack
  retry-ownership guards passed. T14 fallback remains one logical browser request/stream, and no
  replay/dedup contract was fabricated.
- `uv run alembic heads` passed with the single expected head `e9f0a1b2c3d4`. No application
  code, backend route, migration, schema, or T16 work changed. The complete backend regression
  was intentionally not run.
- No feature-hiding skip/xfail/todo was added. The OpenAI SDK cold-start and Celery fresh-process
  import deadline sensitivities remain `DEFERRED_BASELINE_TEST_DEBT`, are not attributed to
  T15, and do not block T15.

State transition:

- T14 remains externally accepted `PASS_WITH_NOTES`.
- T15 moves from `IN_PROGRESS / VERIFY_PENDING` to `AWAITING_ACCEPTANCE /
  EXTERNAL_ACCEPTANCE_PENDING`; external acceptance is required before `PASS`.
- T16 remains `NOT_STARTED` and cannot begin before T15 acceptance.

## T16-IMPLEMENT-START - Enterprise console

Completed: 2026-09-15

Status: `IN_PROGRESS`

Execution Stage: `IMPLEMENT`

- Recovery confirmed the clean `feat/t14-t21-enterprise-hardening` branch at `828caea`.
- Per the explicit user acceptance state for this task, T14 is `PASS_WITH_NOTES`, T15 is `PASS`,
  T16 is `NOT_STARTED` before this transition, and T17 is `NOT_STARTED`.
- The accepted ADR-018 scope is an extension of the existing frontend for Overview, AI,
  Operations, Security, and Compliance. Contract recovery found existing APIs for memberships,
  capability-derived `/me`, approvals/retention, tasks, conversations, alerts/metrics, and agent
  configuration. It found no safe general audit API, async-job/outbox operator API, provider/circuit
  administration API, or provider-secret-management contract.
- T16 therefore starts with a shared capability-aware shell and supported pages only. The backend
  remains authorization authority; no route, schema, migration, secret store, T17 observability,
  or deployment control is added.
- The active plan is `docs/exec-plans/active/T16.md`.

State transition:

- T14 remains externally accepted `PASS_WITH_NOTES`.
- T15 is externally accepted `PASS` by explicit user instruction.
- T16 moves from `NOT_STARTED` to `IN_PROGRESS / IMPLEMENT`.
- T17 remains `NOT_STARTED`.

## T16-IMPLEMENT-CLOSEOUT - Enterprise console

Completed: 2026-09-15

Status: `IN_PROGRESS`

Execution Stage: `VERIFY_PENDING`

- Implemented one shared admin shell with server-derived capability-aware navigation, session and
  direct-route guards, explicit 401/403 handling, and privileged query-cache clearing on logout,
  session invalidation, access denial, and capability changes.
- Added supported Overview, Operations, Security, and Compliance surfaces. The existing AI config
  page was routed into the shell, its mutation controls now require `operations.manage`, its
  destructive rule action uses the shared confirmation dialog, and its requests preserve
  normalized T15 transport errors.
- Added bounded server-paginated conversation metadata, safe review metadata, exact approval
  decisions, and preview-before-execute retention controls. No raw prompt/RAG content, export
  content, secrets, provider keys, unrestricted breaker controls, general audit viewer, async
  retry/cancel control, outbox mutation, or tenant switch was added.
- Frontend verification passed: Prettier format check, ESLint, TypeScript/Vite build, Vitest
  `12 files / 51 tests passed`, focused T15 guards `4 files / 31 tests passed`, and Chromium E2E
  `6 tests passed`.
- Focused backend compatibility tests were attempted but shared setup could not resolve PostgreSQL
  host `db`; this is recorded as environment-only. A direct application inventory check reported
  `136` classified entries and `0` unclassified routes. Alembic reports the single head
  `e9f0a1b2c3d4`; no migration was added.

State transition:

- T14 remains externally accepted `PASS_WITH_NOTES`.
- T15 remains externally accepted `PASS` by explicit user instruction.
- T16 remains `IN_PROGRESS / VERIFY_PENDING`; external verification/acceptance is pending.
- T17 remains `NOT_STARTED`.

## T16-IMPLEMENT-EVIDENCE-CLOSEOUT - Push and focused backend evidence

Completed: 2026-09-15

Status: `IN_PROGRESS`

Execution Stage: `VERIFY_PENDING`

- Pushed the implementation commit normally to `origin/feat/t14-t21-enterprise-hardening`; local
  and remote HEADs were synchronized at `696396fa80dc3ecf01a6d36d9d6e30cf56b83a6b` before this
  docs-only evidence update.
- Recovered the canonical repository Compose test path without touching the unrelated containers
  that occupied host ports 5432 and 6379. The evidence used the same Compose PostgreSQL and Redis
  services on loopback-only ports, the disposable `test_t16_evidence_20260915` database, current
  migrations through `e9f0a1b2c3d4`, existing non-login runtime/maintenance capability roles, and
  Redis DB 15. No production database was used.
- Focused authorization evidence passed: `8` tests covering unauthenticated 401, unauthorized
  capability 403, authorized access, cross-tenant/direct backend denial, role and membership
  revocation with the same JWT, stale/forged role claims, and read-versus-mutation scope.
- Focused compliance evidence passed: `5` tests covering approval API decisions, unauthorized and
  self approval, requester access loss, expiry, rejection, cross-tenant denial, exact operation
  binding, separation of duties, and single-use/idempotent sensitive export execution.
- Implemented endpoint smoke passed: `4` tests covering admin task visibility, conversation metadata,
  dashboard summary, and AI configuration reads. Async-job/outbox controls and provider/circuit
  administration remained unexecuted backend gaps as documented by T16 scope.
- Reconfirmed `136` classified route entries with `0` unclassified HTTP/WS routes, one Alembic head
  `e9f0a1b2c3d4`, no migration, and a clean working tree before the docs-only update. No application
  code or test file changed; no new T16 debt was added.

State transition:

- T14 remains externally accepted `PASS_WITH_NOTES`.
- T15 remains externally accepted `PASS` by explicit user instruction.
- T16 remains `IN_PROGRESS / VERIFY_PENDING`; external verification/acceptance is pending.
- T17 remains `NOT_STARTED`.

## T16-VERIFY - Enterprise Console final verification

Completed: 2026-09-15

Status: `AWAITING_ACCEPTANCE`

Execution Stage: `EXTERNAL_ACCEPTANCE_PENDING`

- Preflight confirmed branch `feat/t14-t21-enterprise-hardening`, clean working tree, and local
  HEAD equal to `origin/feat/t14-t21-enterprise-hardening` at `7852fc0b5b37d7df84d0f676c1cb1044f3b6a1e0`.
- Final scope review confirmed Overview, AI, Operations, Security, Compliance, one shared shell,
  capability-aware navigation, and supported existing workspaces only. General audit, async
  job/outbox, provider/circuit administration, tenant switching, and T17-T20 work remain deferred.
- Focused Chromium acceptance passed `5` tests: authorized overview/operations navigation,
  capability-denied direct route, explicit backend 403, compliance approval confirmation/CSRF/state
  refresh, and browser-session login/logout.
- T16-targeted frontend tests passed `23` tests in `5` files. Format check, lint, explicit
  TypeScript check, and production build passed. The complete 51-test frontend suite was not rerun.
- Compact backend smoke passed `8` tests: authorization allow/deny (`3`), compliance approval and
  requester access-loss behavior (`2`), and conversation/dashboard/AI reads (`3`). The full
  backend suite and deferred baseline timing tests were not run.
- Structural review confirmed server-derived capabilities, backend authorization authority, scoped
  privileged-cache clearing/invalidation, canonical T15 cookie/CSRF transport, no browser Bearer,
  token storage, token URL, secret rendering, fake production records, or unsupported controls.
- Route inventory reported `136` classified entries and `0` unclassified HTTP/WS routes. Alembic
  reported the single head `e9f0a1b2c3d4`; no migration or historical migration modification was
  added. No application code or test file changed during VERIFY.

State transition:

- T14 remains externally accepted `PASS_WITH_NOTES`.
- T15 remains externally accepted `PASS` by explicit user instruction.
- T16 moves from `IN_PROGRESS / VERIFY_PENDING` to `AWAITING_ACCEPTANCE /
  EXTERNAL_ACCEPTANCE_PENDING`; Codex does not mark it `PASS`.
- T17 remains `NOT_STARTED`.
