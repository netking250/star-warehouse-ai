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

## T17-IMPLEMENT - Production observability hardening

Completed: 2026-09-16

Status: `IN_PROGRESS`

Execution Stage: `IMPLEMENT`

- Recovered the frozen T17 scope from the explicit stage instruction because the repository ledgers
  had no narrower T17-specific plan. The existing OpenTelemetry, Prometheus/Mimir, Grafana,
  Loki/Promtail, Tempo, and Alertmanager architecture remains the source of truth.
- Confirmed the implementation boundaries before editing: T02 trusted request/task context, T03/T04
  outbox/RabbitMQ/Celery delivery, T12 conversation transitions, T13/T14 model policy, and T11 audit
  storage remain authoritative. T18 CI/CD, T19 deployment, T20 performance/DR, T16 UI expansion,
  migrations, and deferred OpenAI/Celery timing debt remain out of scope.

State transition:

- T14 remains externally accepted `PASS_WITH_NOTES`.
- T15 and T16 remain `PASS` by explicit user instruction.
- T17 moves from `NOT_STARTED` to `IN_PROGRESS / IMPLEMENT`.
- T18 remains `NOT_STARTED`.

## T17-IMPLEMENT-CLOSEOUT - Production observability hardening

Completed: 2026-09-16

Status: `IN_PROGRESS`

Execution Stage: `VERIFY_PENDING`

- Implemented bounded HTTP, Celery/async-job, outbox, conversation, model gateway/failure-policy,
  circuit, dependency-health, and aggregate database query/pool/error metrics. Logical model
  requests remain distinct from provider attempts, and no tenant/user/request/conversation/run/
  prompt/URL/exception-message metric labels were introduced.
- Hardened JSON application logging and WebSocket/error paths with safe correlation/trace fields,
  recursive redaction, and no default credential, token, prompt, completion, RAG, or sensitive body
  emission. Added bounded OTel resources/limits/batching and safe W3C/TaskEnvelope async context
  propagation without changing task ACK/retry, outbox, or conversation state semantics.
- Added three real-metric Grafana dashboards, eleven T17 direct-provisioned alert rules, local
  no-op Alertmanager routing, validated datasource provisioning, and concise observability runbooks.
  Corrected only pinned-image-compatible Mimir/Tempo/Promtail local Compose configuration issues;
  the stack topology and security boundaries were preserved.
- Focused T17 instrumentation/provisioning, structured logging, model policy, monitoring regression,
  intent subset, and context subset tests passed (`273` tests total after the database telemetry
  check was added). Ruff format/check, ty, route inventory, compile/import, Prometheus/
  Alertmanager/OTel/Compose validation, Grafana provisioning, and Alembic head checks passed. The
  existing observability DB/client fixture cases and cache suite's unavailable `db` host setup
  remain unexecutable and were not counted as T17 implementation failures.
- Local stack smoke passed for Prometheus, Mimir, Grafana, Loki, Tempo, Alertmanager, Collector, and
  Promtail. A deterministic synthetic backend failure produced a valid Loki JSON event and ERROR
  Tempo trace correlated by `t17-correlation-valid` with trace ID
  `9c58ee24122fb45fd341c6bf1bf889bc`; the live repository API scrape was not started because an
  unrelated container occupied host port 8000, while metric-registry assertions passed.

State transition:

- T14 remains externally accepted `PASS_WITH_NOTES`.
- T15 and T16 remain `PASS` by explicit user instruction.
- T17 moves from `IN_PROGRESS / IMPLEMENT` to `IN_PROGRESS / VERIFY_PENDING`; external verification
  and acceptance are pending.
- T18 remains `NOT_STARTED`.

## T17-VERIFY - Production observability acceptance

Attempted: 2026-09-16

Status: `NOT_ACCEPTED`

Primary classification: `TRACE_PROPAGATION_FAILURE`

- Preflight confirmed the required branch, clean worktree, and synchronized local/origin HEAD
  `5c89b5eb3ead887389c7941572921a1f1eeeb149`.
- Started the canonical API, worker, scheduler, outbox relay, PostgreSQL, Redis, RabbitMQ, and
  Qdrant services in a disposable isolated Compose project. The existing monitoring stack remained
  ready; all disposable containers, volumes, and temporary override files were removed afterward.
- Prometheus scraped the canonical API and observed `http_requests_total` for normalized route
  `/api/v1/login` with bounded labels. The API container had
  `OTEL_EXPORTER_OTLP_ENDPOINT` configured to the running Collector.
- A real API request with valid W3C `traceparent` and `X-Correlation-ID` did not return `X-Trace-ID`.
  Tempo contained `star-warehouse-ai-scheduler` traces from the same Collector but no
  `star-warehouse-ai-api` trace. The HTTP trace-correlation acceptance gate therefore failed.
- No code was changed during VERIFY. Canonical Prometheus configuration was restored and the
  monitoring stack remained ready. T17 stays `IN_PROGRESS / VERIFY_PENDING` pending correction and
  a fresh verification attempt.

State transition:

- T14 remains externally accepted `PASS_WITH_NOTES`.
- T15 and T16 remain `PASS` by explicit user instruction.
- T17 remains `IN_PROGRESS / VERIFY_PENDING`; external acceptance is not ready.
- T18 remains `NOT_STARTED`.

## T17-FIX - Restore API HTTP trace export and correlation

Completed: 2026-09-16

Status: `IN_PROGRESS`

Execution Stage: `VERIFY_PENDING`

Primary root cause: `API_TELEMETRY_INITIALIZATION_ORDER`

- Preflight confirmed clean, synchronized branch `feat/t14-t21-enterprise-hardening` at
  `a1a46cd7d7bc12d430def44dd3966b59dfbc198e` before the focused correction.
- The canonical API/dependency services ran in a disposable Compose project against the existing
  Collector/Tempo stack. Five sampled API requests reproduced the failure (`5/5` Tempo `404`, no
  `X-Trace-ID`) while scheduler traces remained queryable.
- Installed source inspection proved FastAPI instrumentation replaced `build_middleware_stack`
  only after Starlette had already cached the live stack on lifespan entry. The existing SDK
  provider, batch processor, OTLP gRPC endpoint, Collector, Tempo, and scheduler path were valid.
- Moved the existing API provider/instrumentation bootstrap after app assembly and before the first
  ASGI call. Attached the existing correlation filter to the shared handler because propagated
  child records do not execute root logger filters. No new tracing abstraction or header was added.
- Post-fix evidence passed `5/5` Tempo API traces with matching existing `X-Trace-ID` values and
  bounded service identity `star-warehouse-ai-api`. A synthetic tenant-resolution request linked
  the normalized HTTP metric, Loki JSON log, and Tempo trace through correlation ID
  `t17-fix-correlation-proof-205` and trace ID `17000000000000000000000000000205`.
  Scheduler traces still reached Tempo. Synthetic password/username Loki searches returned zero.
- Focused tests passed `17`; Ruff, format, ty, disposable Compose validation, route inventory
  (`136` classified, `0` unclassified), and Alembic head `e9f0a1b2c3d4` passed. No migration,
  route, Collector configuration, T02/T03/T04 semantics, deferred timing debt, or T18 work changed.
  The disposable project, synthetic volumes, and temporary evidence files were removed.

State transition:

- T14 remains `PASS_WITH_NOTES`; T15 and T16 remain `PASS`.
- T17 remains `IN_PROGRESS / VERIFY_PENDING` and is ready to resume VERIFY.
- T18 remains `NOT_STARTED`.

## T17-VERIFY-EVIDENCE - Disposable fixture acceptance closeout

Completed: 2026-09-16

Status: `AWAITING_ACCEPTANCE`

Execution Stage: `EXTERNAL_ACCEPTANCE_PENDING`

- Preflight confirmed the synchronized `feat/t14-t21-enterprise-hardening` branch at the accepted
  T17 fix head with a clean worktree. The evidence run used only the disposable
  `star-warehouse-ai-t17evidence` Compose project and existing test factories; no production or
  long-lived developer database was used.
- One authorized disposable tenant/principal and one order/refund approval exercised the real API
  -> transactional outbox -> relay -> RabbitMQ test vhost -> Celery path. Two outbox events were
  published and two worker receipts completed. API, outbox, and worker spans shared trace
  `b418288a455fd6f29ac25035c52f4222` with the accepted parent/child relationship. ACK, retry, and
  idempotency semantics were unchanged.
- The fixed HTTP smoke, deterministic failure metric/log/trace correlation, mock model logical
  request versus provider-attempt/fallback/retry counts, circuit state/rejection/probe signals,
  and T12 one-terminal runtime guards passed. Twenty-nine compact semantic tests passed (`29/29`).
- Stopping only optional Tempo left the business transaction and async delivery successful; the
  Collector's bounded retry/queue behavior was observed, Tempo was restored, and the trace was
  queryable again. Runtime metric-family and Loki-label reviews found no unbounded or sensitive
  identifiers. Four synthetic sentinels were absent from logs, Loki, and traces.
- Three Grafana dashboards loaded, representative real-metric queries evaluated successfully, all
  eleven T17 rules were loaded by the running Grafana rule engine, and Alertmanager loaded its
  local-no-op routing without production credentials. The canonical Mimir endpoint returned
  successful NoData for T17 families because its pre-existing scrape target is a separate
  host-port service; isolated API registry/source evidence remained valid.
- Disposable tenant/user/outbox/receipt counts were zero before teardown, RabbitMQ queues were
  empty, and the disposable containers/network/volumes were removed. Monitoring containers
  remained running. Ruff, format, ty, Compose, Prometheus/rules, Alertmanager, OTel, route
  inventory, and Alembic checks passed; route inventory stayed at `136` classified and `0`
  unclassified with single head `e9f0a1b2c3d4`. No code, migration, route, frontend, T18 work, or
  deferred OpenAI/Celery timing-debt repair changed.

State transition:

- T14 remains `PASS_WITH_NOTES`.
- T15 and T16 remain `PASS` by explicit user instruction.
- T17 moves from `IN_PROGRESS / VERIFY_PENDING` to `AWAITING_ACCEPTANCE /
  EXTERNAL_ACCEPTANCE_PENDING`; Codex does not mark it `PASS`.
- T18 remains `NOT_STARTED`.

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

## T18-IMPLEMENT-CLOSEOUT - Enterprise CI/CD and Software Supply Chain

Completed: 2026-09-16

Status: `IN_PROGRESS`

Execution Stage: `VERIFY_PENDING`

- Recovered the mandatory T18 state from `PROJECT_STATE.md`, `ROADMAP.md`, `DECISIONS.md`, the
  latest relevant execution log, the active plan, root instructions, architecture guardrails, and
  repository README. Recovery started from a clean, synchronized
  `feat/t14-t21-enterprise-hardening` worktree at `5dd8bde`; no branch, PR, merge, or main rule was
  changed.
- Preserved the accepted Brand & docs, Backend quality, Backend tests, Frontend, and Docker smoke
  job families. Hardened checkouts, lock checks, migration-head checks, frozen installs, explicit
  Python 3.12/Node 22/uv 0.6.5/npm 11.9.0, PR cache isolation, bounded JUnit/coverage artifacts,
  clean-checkout Docker role provisioning, non-root/image-secret checks, and OCI source metadata.
- Added `.github/workflows/supply-chain.yml`, `dependency-review.yml`, and `codeql.yml`; retained
  Dependabot and added Docker ecosystem coverage. PR workflows remain read-only and secret-free;
  no `pull_request_target` exists. Trusted provenance is configured only for `main`/tag pushes with
  narrowly scoped attestation permissions. Registry publication and image signing remain deferred.
- Added redacted current-checkout Gitleaks SARIF, locked backend/frontend audit reports, archive-
  based Trivy image JSON, CycloneDX JSON SBOM, image metadata, and 14-day artifacts. Third-party
  scanner containers receive no Docker daemon socket. The exact synthetic `sk-test` fixture value
  is the only secret-scan allowlist entry.
- Local evidence passed: repository identity; workflow YAML parsing; pinned actionlint across all
  workflows; `uv lock --check`, Ruff lint/format, ty, Alembic single head
  `e9f0a1b2c3d4`; frontend npm frozen install, format, lint, Vitest (51 tests), and build; hardened
  Docker build/non-root/metadata/credential inspection; disposable Compose migration, role
  provisioning, and health smoke; Gitleaks (0 current-checkout findings); CycloneDX parse (1.6,
  255 components); and hardened Trivy scan (0 critical, 81 high, 37 high with known fixes).
- The frozen dependency audits intentionally did not change lockfiles: pip-audit reported 83 records
  across 19 packages without severity fields in its JSON format; npm audit reported 9 high, 4
  moderate, 1 low, and 0 critical. These findings remain visible as warnings and artifacts, while
  critical findings block and PR Dependency Review blocks new high/critical dependency deltas. The
  pre-update image's critical Debian findings were removed by the bounded base-image security-update
  step; no suppressions were added.
- The broader backend fixture smoke was limited by the local environment's unavailable `db`
  hostname; focused branding smoke passed. The full backend suite, hosted protected-PR proof, and
  trusted hosted attestation were intentionally deferred to VERIFY/T21. OpenAI cold-start and
  Celery fresh-process timing debt was not changed.

State transition:

- T14 remains externally accepted `PASS_WITH_NOTES`.
- T15, T16, and T17 remain accepted `PASS` by the explicit T18 implementation instruction.
- T18 remains `IN_PROGRESS / VERIFY_PENDING`; external verification is required and Codex does not
  mark it `PASS`.
- T19 and T20 remain `NOT_STARTED`.

## T18-VERIFY-CLOSEOUT - CI/CD and Software Supply Chain final verification

Completed: 2026-09-16

Status: `AWAITING_ACCEPTANCE`

Execution Stage: `EXTERNAL_ACCEPTANCE_PENDING`

- Preflight reconfirmed the required integration branch, a clean worktree, and local/remote
  synchronization at implementation HEAD `940189b0d5db078d55c89147b27c2356a064bd89`. No PR,
  merge, main-rule change, registry publication, deployment, T19, or T20 work occurred.
- Workflow review passed: all workflow defaults are `contents: read`; no `pull_request_target`; no
  untrusted PR secrets, OIDC, package/release writes, or attestation writes; only CodeQL
  `security-events: write` and trusted main/tag provenance `id-token: write`/`attestations: write`.
  Third-party action pinning, dangerous-pattern review, credential persistence, cache conditions,
  and job dependency semantics passed. Actionlint 1.7.7 reported zero errors.
- Determinism passed for Python 3.12, Node 22, uv 0.6.5, npm 11.9.0, uv frozen/lock checks, npm
  ci, clean archive identity/lock checks, and altered-copy lock-mismatch failure fixtures. The
  five accepted gate families remain separate. Backend quality passed; representative backend
  smoke passed; frontend format/lint/Vitest (`12` files / `51` tests)/build passed; Docker rebuilt,
  ran non-root, imported with synthetic-only settings, and passed image secret-path inspection.
- Gitleaks reported zero current-checkout findings with redacted SARIF. A non-documentation
  synthetic sentinel was detected and failed the scanner as expected. CycloneDX JSON 1.6 parsed with
  `255` components and matched representative packages in the scanned image. OCI revision metadata
  matched the implementation build commit and contained no secrets.
- Machine-readable vulnerability evidence remains visible: npm `0` critical / `9` high / `4`
  moderate / `1` low; pip-audit `83` records across `19` packages with no severity field; Trivy
  `0` critical / `81` high, including `37` high records with known fixes. Grouped package IDs,
  runtime/dev scope, fixes, and dispositions are recorded in the active plan. No suppressions or
  bulk upgrades were introduced. Critical npm/image findings and invalid/reportless scanner output
  fail their policy; existing highs remain documented warnings.
- The protected-PR and trusted-hosted-attestation runs are `NOT YET EXECUTED` by design and remain
  mandatory `T21 FINAL GATE` evidence. The OpenAI cold-start and Celery import timing debts remain
  untouched deferred baseline debt. No new T18 debt was introduced.

State transition:

- T14 remains `PASS_WITH_NOTES`.
- T15, T16, and T17 remain accepted `PASS` by the explicit T18 instruction.
- T18 moves from `IN_PROGRESS / VERIFY_PENDING` to `AWAITING_ACCEPTANCE /
  EXTERNAL_ACCEPTANCE_PENDING`; Codex does not mark it `PASS`.
- T19 and T20 remain `NOT_STARTED`.

## T19-IMPLEMENT-CLOSEOUT - Production Deployment Baseline

Completed: 2026-09-17

Status: `IN_PROGRESS`

Execution Stage: `VERIFY_PENDING`

- Recovered the frozen deployment scope from ADR-015/ADR-016, engineering ledgers, T17/T18
  documentation, Docker/Compose/runtime configuration, startup/migration/probe contracts, and the
  existing deployment inventory. No competing Helm, Kubernetes, Terraform, or application
  deployment system existed; there was no scope conflict.
- Added one canonical Helm chart for the existing API, tenant worker, maintenance worker,
  singleton scheduler, and conservative singleton outbox relay. The chart consumes one prebuilt
  image, prefers a digest, rejects missing production digests and non-overridden `latest`, exposes
  only the API, references rather than creates secrets, and keeps normal pods non-root with no
  privilege escalation, host namespaces/paths, RBAC, or service-account token.
- Added a revision-scoped migration Job as the sole `alembic upgrade head` owner. Workload init
  checks are non-mutating, and the Job grants only read access to `alembic_version` to the runtime
  and maintenance logins. API replicas never migrate; Helm rollback does not downgrade the schema
  or delete PVCs.
- Added TLS ingress profiles for k3s Traefik and production-reference nginx behavior, exact public
  origin/OIDC configuration, upload and bounded streaming timeouts, internal-only metrics and
  infrastructure, resource/probe/lifecycle defaults, config checksums, private pull-secret support,
  and PVC-backed demo PostgreSQL/Redis/RabbitMQ/Qdrant with non-root-compatible writable paths.
- Extended the trusted T18 workflow so only successful `main`/version-tag runs publish the exact
  scanned image to GHCR under immutable commit/version tags, resolve its digest, attest that
  subject, and preserve a short-lived image-reference artifact. Pull requests do not publish and
  `latest` is never created.
- Added bounded validation/deployment scripts and operator documentation for Helm, low-cost k3s,
  secret keys, migrations, upgrades/rollbacks, failure visibility, browser security, T17 telemetry,
  trusted artifacts, and the AWS reference mapping (EKS/ALB, RDS PostgreSQL, ElastiCache-compatible
  Redis, Amazon MQ for RabbitMQ, self-hosted/managed Qdrant, S3, Secrets Manager/External Secrets,
  and ECR/GHCR boundary). No AWS resource or alternate IaC stack was created.
- Helm 3.17.3 lint/template passed for default, demo, and production reference. Kubeconform 0.6.7
  against Kubernetes 1.30 reported `38` valid resources with `0` invalid/errors/skipped. ShellCheck
  0.11.0, actionlint 1.7.12, image-negative cases, and the rendered manifest security/secret scan
  passed.
- A disposable k3d 5.9.0 node running actual k3s `v1.35.5+k3s1` passed complete install, the
  revision migration, all application/dependency readiness, HTTPS `/health`, service endpoints,
  internal metrics, structured API/worker logs, query-token WebSocket rejection, a benign upgrade,
  application rollback without schema downgrade, and a missing application Secret failure that
  was recorded failed and atomically recovered to deployed revision 8. PVCs remained intact.
- OCI metadata inspection confirmed the reused T18 image is non-root and carries version `5.0.0`,
  source repository, and revision `8802702b8efbe636e6ba3c92dc889c3ee01650b5`. Direct route
  inventory remained `136` classified entries with `0` unclassified; Alembic remained the single
  head `e9f0a1b2c3d4`. No application route, business code, or migration changed.
- Hosted GHCR runtime/attestation evidence remains deferred to T21. The disposable run proves k3s
  behavior, while a real public VM/DNS/CA deployment remains environment-specific VERIFY evidence.
  OpenAI/Celery timing debt and the T18 vulnerability baseline were not changed. No T20
  performance, resilience, backup/restore, DR, or capacity work was performed.

State transition:

- T14 remains `PASS_WITH_NOTES`; T15, T16, and T17 remain `PASS`; T18 remains
  `PASS_WITH_NOTES` by explicit user instruction.
- T19 remains `IN_PROGRESS` and advances from `IMPLEMENT` to `VERIFY_PENDING`; Codex does not mark
  it `PASS`.
- T20 remains `NOT_STARTED`; no PR or merge is created before T21.

## T19-VERIFY-CLOSEOUT - Deployment Baseline Final Verification

Completed: 2026-09-17

Status: `AWAITING_ACCEPTANCE`

Execution Stage: `EXTERNAL_ACCEPTANCE_PENDING`

- Final verification recovered a clean, synchronized `feat/t14-t21-enterprise-hardening` branch at
  `31536460a808cffa3847261d4db681a2086b9eb9`. No production namespace, database, credential, AWS
  resource, production image publication, PR, merge, application business code, route, or migration
  history was changed.
- Independent Helm 3.17.3 lint/template passed for default, demo, and production-reference values.
  Strict kubeconform 0.6.7 against Kubernetes 1.30 reported `38` valid resources and `0` invalid,
  errors, or skipped. ShellCheck 0.11.0 passed for deployment scripts. Production render scans found
  zero privileged/host access, cluster-admin, plaintext Secret object, public infrastructure service,
  or `latest` image. Digest precedence, missing production digest, and default `latest` negative
  cases failed as designed.
- Fresh disposable k3d `5.9.0` with actual k3s `v1.35.5+k3s1` and isolated namespace `t19-verify`
  passed canonical install, migration completion, API/tenant-worker/maintenance-worker/scheduler/
  relay readiness, demo dependency readiness, TLS ingress health, internal metrics, public metrics
  denial, browser session/CSRF/Origin behavior, WebSocket security, and small authenticated upload.
  A stale broker-host value from the discarded first non-canonical test fixture was corrected only in
  the disposable Secret; the final chart-declared Service names and all worker processes recovered.
- A benign Helm upgrade with API replicas `2` succeeded and ran one revision-scoped migration owner
  with parallelism/completions `1/1`. Deliberate invalid-PostgreSQL and missing-`SECRET_KEY` tests
  returned visible non-zero failures and atomically recovered. Application rollback succeeded at
  Helm revision `7`; no `alembic downgrade`, PVC/namespace deletion, or database restore occurred.
  PostgreSQL remained at `e9f0a1b2c3d4`.
- Effective app security was UID/GID `999`, non-root, no privilege escalation, no privileged/host
  namespace/path access, no service-account API token, and bounded termination. Scheduler and relay
  remained singleton. The API startup/readiness/liveness and process-lifecycle probes matched their
  documented semantics; provider keys were empty while API readiness remained healthy.
- T17 Helm telemetry smoke reached the existing Collector/Tempo endpoint. One API request returned
  a trace ID and its four-span `star-warehouse-ai-api` trace was queryable in Tempo; internal API
  metrics and API/maintenance-worker JSON logs were present. A maintenance task trace was queryable,
  and disposable Secret sentinels had zero log/trace matches. Existing scheduled maintenance-task
  `TenantContextMissingError` records are a non-blocking `PRE_EXISTING_BASELINE` observation in the
  reused T18 image, not a T19 Helm defect; no application repair was made during VERIFY.
- No deterministic runtime Mock-provider stream fixture is wired into the chart, so SSE completion
  was not claimed and no real provider was called. Effective production buffering/body/120-second
  ingress settings were verified separately. Hosted GHCR runtime/attestation, public VM/DNS/CA,
  live AWS deployment, T20 performance/resilience/backup/restore/DR/capacity work, and existing
  OpenAI/Celery timing debt remain deferred.

State transition:

- T14 remains `PASS_WITH_NOTES`; T15, T16, and T17 remain `PASS`; T18 remains `PASS_WITH_NOTES` by
  explicit user instruction.
- T19 moves from `IN_PROGRESS / VERIFY_PENDING` to `AWAITING_ACCEPTANCE /
  EXTERNAL_ACCEPTANCE_PENDING`; Codex does not mark it `PASS`.
- T20 remains `NOT_STARTED`; no PR or merge is created before T21.

## T20-IMPLEMENT-CLOSEOUT - Performance, Failure, Backup, Restore, and DR

Completed: 2026-09-17

Status: `IN_PROGRESS`

Execution Stage: `VERIFY_PENDING`

- Recovered T20 from ADR-020 and accepted T03/T04/T06/T07/T11-T14/T17-T19 contracts. Existing
  pytest microbenchmarks were retained; k6 `0.57.0` is the sole concurrent HTTP harness. Scripts
  require explicit non-production targets and destructive confirmation.
- In disposable k3d `5.9.0` / k3s `v1.35.5+k3s1`, three 35-second baselines completed 537/547/527
  requests with zero failures and mean 14.46 requests/s, p50 112.39 ms, p95 412.85 ms, and p99
  604.75 ms. A two-minute short soak completed 1,707 requests with zero failures and no obvious
  bounded-memory runaway. No production capacity/SLA claim was made.
- A real protected refund workflow demonstrated relay and worker backpressure, RabbitMQ publication
  retry, backlog/queue drain, and durable receipt idempotency. Eighteen effects survived backup;
  one more completed after restore. No committed data, Outbox intent, or tenant isolation was lost.
- API/scheduler/worker/relay and PostgreSQL/Redis/RabbitMQ/Qdrant failures were injected one at a
  time and recovered. Mock-provider retry/fallback/circuit/degradation and deterministic
  conversation terminal/cancellation tests passed. T17 metrics and correlated JSON logs made load
  and broker/dependency failures visible; the optional sink-absent smoke did not block business.
- Added the Helm demo backup CronJob/bootstrap Job/dedicated PVC and guarded fresh-target restore.
  The live drill found and fixed an absolute checksum-path defect and missing logical-backup ACL
  restoration. The corrected restore preserved fixed least-privilege roles, RLS, Alembic
  `e9f0a1b2c3d4`, application login, 100/25 tenant rows with zero cross-tenant visibility, audit
  sentinels, 18 async effects, and post-restore processing. Restore took 6 seconds; service became
  ready in approximately 80 seconds in this disposable environment.
- PostgreSQL is authoritative; Qdrant is rebuildable; Redis is ephemeral; RabbitMQ is a durable
  secondary behind Outbox. Active local uploads are not durable in T19 `emptyDir`, so object-store
  recovery remains documented rather than claimed. Demo RPO is the latest completed backup and
  PITR is not implemented. Single-node pod recovery is not node HA.
- The exact source namespace/PVCs and final disposable cluster/network/volume/k6 containers were
  removed. Production/shared developer persistence, public cloud, real providers, application
  routes, and migrations were untouched.

State transition:

- T14 and T18 remain `PASS_WITH_NOTES`; T15-T17 remain `PASS`; T19 remains externally accepted
  `PASS_WITH_NOTES` by the T20 instruction.
- T20 remains `IN_PROGRESS` and advances to `VERIFY_PENDING`; Codex does not mark it `PASS`.
- T21 remains `NOT_STARTED`; no PR or merge was created.

## T21-IMPLEMENT-BLOCKED - Final Integration Test Environment

Recorded: 2026-09-17

Status: `IN_PROGRESS`

Execution Stage: `IMPLEMENT_BLOCKED`

- Recovered the clean, synchronized integration branch at
  `d7acd74d0fddc9b4b539c8c8300c37617660b1d4`; reconciled T15-T20 accepted plan locations and
  preserved all accepted notes.
- Added a provider-free deterministic workflow evaluation inside the existing evaluation package,
  with 12 synthetic scenarios and objective routing, tool, approval, authorization, tenant,
  fallback, and terminal metrics. The command passed 12/12 and focused tests passed 3/3.
- Added the final system view, case study, evidence index, interview guide, limitation register,
  offline-evaluation guide, README links, and an unsubmitted final-PR draft. No PR, merge, release,
  provider call, migration, or platform feature was created.
- Fresh migration validation reached the single accepted Alembic head `e9f0a1b2c3d4`.
- The one authorized canonical full backend attempt collected 1,848 tests but was stopped at 5%
  after widespread PostgreSQL connection timeouts crossed API and agent tests. A focused diagnostic
  failed with `asyncpg` `TimeoutError` in 79.87 seconds. Direct probes proved `localhost` timed out
  on this Windows/Docker host while `127.0.0.1` reached the same healthy database immediately;
  PostgreSQL had no lock wait. Classification: `TEST_ENVIRONMENT`.
- The full suite was not rerun under the explicit one-run constraint. Aggregate full-suite counts,
  coverage, final frontend/Docker/Helm/route/security gates, remote synchronization, and final PR
  readiness are therefore not claimed. T21 remains in progress and does not advance to VERIFY.

## T21-IMPLEMENT-EVIDENCE-BLOCKED - Replacement Full Regression

Recorded: 2026-09-17

Status: `IN_PROGRESS`

Execution Stage: `IMPLEMENT_BLOCKED`

- The prior interrupted run remains documented as invalid/incomplete `TEST_ENVIRONMENT` evidence:
  `localhost` PostgreSQL timed out while `127.0.0.1` succeeded.
- The explicitly authorized replacement used the corrected `127.0.0.1` endpoint, a fresh isolated
  database migrated to `e9f0a1b2c3d4`, writable OS temp/cache paths, Redis DB 15, a process-scoped
  Qdrant collection, memory Celery transports, and no real provider calls. Three focused preflight
  tests passed: migration single-head, tenant-filtered DB access, and unauthenticated protected API.
- The canonical full backend command ran exactly once to completion: 1,848 collected, 1,810 passed,
  1 failed, 0 errors, 37 skipped, 81.93% coverage, and 2,231.21 seconds (37:11). The single failure
  was `tests/test_chat_api.py::test_chat_timeout_after_answer_closes_without_error`.
- A focused diagnostic reproduced that failure in 5.84 seconds. The stream emitted a timeout error
  before the expected token after answer; this is not either accepted OpenAI/Celery timing debt and
  not a PostgreSQL connectivity issue. T21 did not change chat code and no repair was made.
  Classification: `FEATURE_REGRESSION`.
- Final frontend, Docker, Helm, route, security, CI, and PR-readiness gates were intentionally not
  started after the feature regression. T21 remains `IN_PROGRESS / IMPLEMENT_BLOCKED`; no PR or
  merge was created.

## T20-VERIFY-CLOSEOUT - Resilience, Backup, Restore, and DR Final Verification

Completed: 2026-09-17

Status: `AWAITING_ACCEPTANCE`

Execution Stage: `EXTERNAL_ACCEPTANCE_PENDING`

- Verification began from clean, synchronized implementation head `8c55131a16d81eed7521d8095ae96a43e66dece9`
  on `feat/t14-t21-enterprise-hardening`. Only disposable k3d cluster `t20v-20260917` (`k3d 5.9.0`,
  `k3s v1.35.5+k3s1`) and namespaces `t20-verify`/`t20-restore` were used. Synthetic credentials,
  deterministic tenants, and the Mock/provider-free path were used; production, persistent developer
  data, shared Redis/RabbitMQ/Qdrant, real providers, and object storage were not touched.
- Harness safety passed: default profile is SMOKE (`1 VU/10s`), BASELINE requires explicit selection and
  credentials, no real provider URL/key is present, and no destructive workflow is in the k6 script.
  One SMOKE passed with 39 requests and 100% checks. One explicit BASELINE spot-check passed 587/587
  checks at 15.355985 req/s, p50 94.176886 ms, p95 355.744690 ms, p99 840.389933 ms. API memory was
  246->260 MiB, worker memory 207->205 MiB, and PostgreSQL activity was 9 connections. Throughput and
  p95 were not worse than the implementation mean; the single-run p99 was an endpoint-tail variance.
  No production capacity/SLA claim is made.
- Async integrity spot-check passed 5/5 produced/completed effects, zero lost work, zero duplicate durable
  effects, 5 unique receipts, zero pending Outbox rows, and drained RabbitMQ business queues. Worker
  outage sample queued 3 published messages while the worker was stopped and completed all 3 after
  restart with unique receipts. Relay pause sample left 3 committed rows pending and unpublished, then
  drained all 3 after recovery. PostgreSQL outage returned HTTP 500 for a valid login rather than false
  success, logged the connectivity failure, then recovered login/protected read and a 5-connection pool.
- Backup reproduction used the canonical demo CronJob/manual Job procedure. The selected fresh artifact
  was 296047 bytes with SHA-256
  `b15649b212f6a4b903f021f50cd7b6ba4187a0a2f3453b38c1b5e4ae014187d7`. Metadata contained timestamp,
  application `5.0.0`, image revision `8c55131a16d81eed7521d8095ae96a43e66dece9`, Alembic
  `e9f0a1b2c3d4`, disposable database identifier, and `postgresql-logical-custom` type; no credentials
  were present. `pg_restore --list` and non-empty/checksum checks passed.
- Fresh database `t20_restore_verify` restored successfully, ran the normal migration/role mechanism,
  retained Alembic `e9f0a1b2c3d4`, required `plpgsql`, fixed non-login/non-superuser/non-BYPASSRLS
  capability roles, 49 RLS policies, application connectivity, and deterministic sentinels. Tenant A
  saw 2 own orders and 0 tenant-B rows; tenant B saw 1 own order and 0 tenant-A rows. Orders/refunds,
  Outbox/receipt, audit/compliance, and conversation/runtime invariants were preserved; duplicate receipt
  groups were zero.
- Restore-defect regressions were directly exercised. Moving the dump, metadata, checksum, and restore
  script to a new directory passed basename checksum validation and full restore, proving the former
  in-container absolute checksum path cannot recur. A control restore with former `pg_restore --no-acl`
  behavior produced `permission denied for table orders` under `star_warehouse_runtime`; the corrected
  ACL-preserving/policy-derived-grant restore read 2 orders successfully. Neither defect regressed.
- The complete DR replay seeded and backed up the source, destroyed only the disposable source namespace/
  PVCs, created a fresh target, restored, ran migration/role provisioning, started the application,
  validated tenant isolation/invariants, and completed one new post-restore async operation with one
  unique completed receipt and drained queues. From source-destroy initiation at `14:50:39.839 +08:00`
  through async completion at approximately `15:01:45.234 +08:00`, measured local RTO was ~665 seconds
  (11m05s). Tested RPO is the latest completed logical backup; PITR is `NOT IMPLEMENTED`.
- Persistence classification was rechecked. PostgreSQL is `SOURCE_OF_TRUTH`; Qdrant is
  `DERIVED_REBUILDABLE`, with the PostgreSQL/source-file reconciliation seam covered by the focused
  memory consistency tests; Redis is `EPHEMERAL`; RabbitMQ is `DURABLE_SECONDARY` and never an exactly-
  once business source. The active object-storage adapter is absent, T19 uploads use transient `emptyDir`,
  and `OBJECT_STORAGE_RUNTIME_RECOVERY = NOT_EXERCISED`; PostgreSQL backup does not restore uploaded
  source bytes. Production durable uploads require the accepted external S3-compatible contract and
  provider/bucket/versioning/backup responsibility.
- Observability during PostgreSQL outage provided Prometheus HTTP counters, structured JSON error logs,
  trace/span IDs, and a preserved correlation-ID response header. No external OTLP sink was configured,
  so no external trace backend was claimed. Runbook checks found explicit target/confirmation guards,
  no destructive defaults, no downgrade, no `FLUSHALL`, and no silent error masking.
- Focused tests passed 14/14 for disposable PostgreSQL RLS/database roles and 72/72 for T20 assets,
  route/metrics, authorization, Outbox, task-runtime reliability, memory/Qdrant reconciliation,
  migration chain, and selected Celery routing/context. Ruff, format, ty, ShellCheck `0.11.0`, Helm
  lint, route inventory (`136` classified, `0` unclassified HTTP/WS), and single-head checks passed.
  The full backend suite, three-run performance repetition, real providers, known OpenAI/Celery timing
  debts, long soak, public-cloud DR, and frontend suite were not run.
- Cleanup removed both disposable namespaces/PVCs, the named k3d cluster/network/volume, port-forwards,
  temporary credentials, backup, k6 summaries, and the ignored raw verification directory. No PR, merge,
  T21 work, or implementation repair was performed during VERIFY.

State transition:

- T14 remains `PASS_WITH_NOTES`; T15-T17 remain `PASS`; T18 and T19 remain `PASS_WITH_NOTES` by the
  explicit current-state instruction.
- T20 moves from `IN_PROGRESS / VERIFY_PENDING` to `AWAITING_ACCEPTANCE /
  EXTERNAL_ACCEPTANCE_PENDING`; Codex does not mark T20 `PASS`.
- T21 remains `NOT_STARTED`; no PR or merge was created.

## T21-IMPLEMENT-RESUME - Final local readiness gates

Recorded: 2026-09-17

Status: `IN_PROGRESS`

Execution Stage: `VERIFY_PENDING`

- Resumed from the synchronized `feat/t14-t21-enterprise-hardening` branch at
  `efa61acec373f88bc01d9d8e332fea3c7d5919b9`. The accepted T21 backend result was not rerun: the
  completed full regression remains `1848` collected, `1810` passed, `1` historical nondeterministic
  timing failure, `0` errors, `37` skipped, and `81.93%` coverage.
- The failure `tests/test_chat_api.py::test_chat_timeout_after_answer_closes_without_error` was
  recorded as `NON_REPRODUCIBLE_PREVIOUS_FAILURE` through the required A/B control: T21 focused
  control `5/5` passed, accepted T20 `4/5` passed, and protected `origin/main` `4/5` passed with the
  same test. No code in the failing execution path changed. This is a separate historical
  chat-stream timing flake, not the OpenAI or Celery timing debt. Demonstrated T21 feature
  regressions: `0`.
- Frozen frontend gates passed: `npm ci`, format check, lint, explicit TypeScript typecheck, Vitest
  (`12` files, `51` tests), and production build. The meaningful browser suite reported `6/6`
  passing tests covering login/logout, 401/403, protected routes, T15 transport, and T16 console;
  the Windows Vite runner required termination only after all tests completed during teardown.
- A detached clean-checkout production-relevant Docker build passed. Disposable synthetic
  configuration brought up dependencies, ran migration and role provisioning, started the API, and
  passed `/health`. The image ran as `appuser`, had no embedded `.env` or developer credential
  residue, and required neither real-provider nor production credentials; it was not published.
- Helm lint, template, schema, strict kubeconform, and ShellCheck `0.11.0` passed for the final
  chart checks. Kubeconform validated `42` resources. The migration Job is the sole `alembic upgrade
  head` owner; API, worker, scheduler, and relay workloads use only `alembic current --check-heads`.
- The canonical route inventory passed with `126` application HTTP policy routes, `2` classified
  WebSocket routes, and `0` unclassified HTTP/WS routes. Its complete inventory remains `136`
  entries (`130` HTTP including `4` framework routes, `2` WebSocket, and `4` mounts), explaining the
  earlier T19 total without application route removal. The bounded final security spot check found
  no browser Bearer transport, persisted auth token, WebSocket query token, wildcard production CORS,
  plaintext Helm secret, privileged workload, cluster-admin, dangerous `pull_request_target`,
  untrusted PR secret access, or untrusted PR publish/attestation path.
- The CI graph still exposes the five protected gate families `Brand & docs`, `Backend quality`,
  `Backend tests`, `Frontend`, and `Docker smoke`. PR defaults are read-only and trusted
  main/version-tag publication and attestation jobs remain push-guarded. The provider-free offline
  evaluation was reused at `12/12`; no evaluation rerun or real provider call was made.
- Current README, state, roadmap, decisions, architecture, case study, evidence index, interview
  guide, known limitations, T21 plan, and final PR body were reconciled. The PR body is prepared,
  but no PR or merge exists. Hosted PR checks, trusted GHCR publication, attestation, public
  VM/DNS/CA, object-storage recovery, PITR, live AWS, long soak, and production-capacity evidence
  remain pending or unperformed as documented limitations.

State transition:

- T14 remains `PASS_WITH_NOTES`; T15-T17 remain `PASS`; T18-T20 remain `PASS_WITH_NOTES` by the
  explicit current-state instruction.
- T21 remains `IN_PROGRESS` and advances from `IMPLEMENT_BLOCKED` to `VERIFY_PENDING` for final
  external hosted verification. Codex does not mark T21 `PASS` or `AWAITING_ACCEPTANCE`.
- No PR was created, no merge was performed, and the branch remains the long-lived integration
  branch.

## P-UAT-02A-FIX - Knowledge upload / worker storage repair

Started: 2026-09-17

Finished: 2026-09-18

Status: `AWAITING_ACCEPTANCE`

Execution Stage: `EXTERNAL_ACCEPTANCE_PENDING`

- Recovery confirmed a clean worktree, fetched protected `origin/main` at
  `5d84b034513e79557c6ad9ce9fb819832034352f`, and created
  `fix/knowledge-worker-storage` directly from that commit.
- Pre-fix real reproduction uploaded document `3`, persisted
  `uploads/knowledge/tenant/default/128cfb2edc6340798f54b78077163432.txt`, and returned task
  `42d2b16b-2d93-4037-a0b0-130c3ea88ec4`. The API read the 91-byte source with SHA-256
  `f711c8c1705cac8f028b5b44b077f3d0f0e9afe193f360b1376b7ce8c154fd0b`; the tenant worker could
  not stat the same reference and raised `FileNotFoundError`. Both used `/app`, but neither had a
  shared uploads mount. The document reached terminal `failed` after bounded retries.
- Root cause was classified `LOCAL_VOLUME_NOT_SHARED` plus `STORAGE_ADAPTER_CONTRACT_BUG`.
- The repair added a canonical tenant-aware source-object Port/local adapter, stable logical keys,
  namespace validation, atomic writes, deterministic missing-object failure, and idempotent delete.
  API, tenant worker, and maintenance worker now share one local/demo named volume and canonical
  `/app/uploads/knowledge` root. The image pre-creates the mountpoint for non-root `appuser`.
  Scheduler and outbox relay do not receive the source volume.
- Worker payload remains document identity only. The worker reloads metadata and resolves source
  bytes through the canonical adapter before parse/chunk/embed and Qdrant replacement. Retry status
  is `pending` before the last attempt and terminal `failed` after the last attempt.
- Admin deletion and retention use one lifecycle service to remove tenant-scoped Qdrant points and
  source bytes before metadata. Qdrant remains derived/rebuildable.
- Focused pytest passed `30/30`. Focused Ruff, Ruff format, and ty passed. Docker Compose config,
  image build, fresh migrations/role provisioning, startup, and health passed.
- Fresh isolated Compose E2E uploaded `STAR_WAREHOUSE_KB_UAT_SENTINEL_9274` through the real API:
  HTTP 200, document `1`, task `40068d5f-c0da-4ccb-acbd-8f064c5168b8`, document `done`, Celery
  `SUCCESS`, one chunk, and one Qdrant point carrying `tenant_id=default`, `doc_id=1`, source
  `sentinel.txt`, and the sentinel content. API and worker both read 185 bytes with SHA-256
  `d9403452220caa77f389353062ce9548a32701ba52ec9519b0516811540ff109` from the shared volume.
  Re-sync task `d19597da-b287-48d9-90bd-3c87a3fbfe94` also reached `SUCCESS`. A second uploaded and
  synchronized document was deleted; its metadata count, source object, and tenant-filtered Qdrant
  point count were all zero afterward.
- The existing `scripts/seed_data.py` failed in the fresh environment because it does not bind a
  tenant context after T14-T21. This unrelated pre-existing limitation was not changed; the proof
  used real registration plus an isolated local-only administrator promotion.
- No migration, UI change, real model call, production object-store adapter, PR, or merge was made.
  Docker named-volume durability remains local/demo only; production upload recovery remains
  unexercised.

State transition:

- P-UAT-02A-FIX moves from `IN_PROGRESS / FIX_IMPLEMENT` to `AWAITING_ACCEPTANCE /
  EXTERNAL_ACCEPTANCE_PENDING`; Codex does not mark it `PASS`.
- P-UAT-02 remains `NOT_STARTED` pending external acceptance of this repair.

## P-UAT-02-FIX - Summarization Gateway non-streaming semantics

Started: 2026-09-18

Finished: 2026-09-18

Status: `AWAITING_ACCEPTANCE`

Execution Stage: `EXTERNAL_ACCEPTANCE_PENDING`

- Recovery confirmed branch `fix/knowledge-worker-storage`, accepted head
  `dc2e08ec7ce14daf4d07e8cbcfe8b76b763877e7`, and a clean initial worktree. P-UAT-01 and
  P-UAT-02A-FIX were externally reported `PASS_WITH_NOTES`; P-UAT-02 entered this repair as `FAIL`.
- The required red reproduction ran the real `SessionSummarizer` call inside
  `StateGraph.astream_events()` against a chat-only `summarization` candidate. LangChain's inherited
  streaming callback caused public `ainvoke()` to enter `GatewayChatModel._astream()`, request
  `chat + streaming`, and raise the production-equivalent capability error before provider I/O.
- `ModelRequest.required_capabilities`, ModelGateway resolution, ModelFailurePolicy, route config,
  and `SessionSummarizer` were already semantically correct. The minimum adapter repair pins public
  `GatewayChatModel.ainvoke()` to `stream=False` before delegating to LangChain; public `astream()`
  still uses the streaming request and capability set. No resolver, route, summarizer, provider, or
  T14 failure-policy change was made.
- Focused verification passed `95` tests and skipped `1` opt-in real-model test. Coverage included
  chat-only non-streaming success, chat-only streaming rejection before provider I/O,
  streaming-capable success, missing-chat rejection, actual graph-event summarization, normalized
  structured output, durable single-terminal conversation completion, cancellation, bounded global
  timeout, post-visible timeout, duplicate-terminal prevention, and T14 fallback/circuit ownership.
  Scoped Ruff, Ruff format, and ty passed. The full backend suite was intentionally not run.
- The isolated Aurora chat run `cbfb389e-cea3-41d7-8124-5bae5c6a7b0e` reached `COMPLETED` with
  `AURORA-REFUND-17` in provider context, one persisted agent card, one `RUN_COMPLETED`, no
  `RUN_FAILED`, and no duplicate complete response. The deterministic provider returned a safe
  completed terminal message; answer elegance and model quality were not evaluated.
- The dedicated default-tenant private-sentinel run
  `fe54f06b-4b70-47b6-9049-ed84a54d9c79` reached `COMPLETED` with one agent card and one terminal
  event. Provider requests contained only the user's sentinel occurrence and zero Tenant B private
  document heading/sentence; the answer contained no private document content. This supplements the
  already accepted Tenant A retrieval result with zero retained Tenant B evidence.
- Re-syncing `east-harbor-shipping.txt` completed successfully, kept its exact tenant-scoped Qdrant
  point count at `1 -> 1`, and preserved Top-1 retrieval at `0.99`. Real API deletion of
  default-tenant `orbit-lamp-general.txt` removed the DB row, source object, and point (`1 -> 0`).
  Deleted document text did not enter post-delete provider context, three unrelated tenant points
  remained, and Aurora remained Top-1 at `0.95`.
- The previous `Event loop is closed` warning did not reproduce in recent app/worker logs and caused
  no observed state, task, or resource impact; it remains `NON_BLOCKING_DIAGNOSTIC`.
- Browser proof under OS temp
  `C:\Users\11\AppData\Local\Temp\star-warehouse-ai-p-uat-02-fix-20260918-173240` shows synchronized
  documents in Admin Knowledge and a completed Aurora customer chat. The clean browser capture had
  zero console errors, HTTP 4xx, HTTP 5xx, or runtime exceptions. Screenshots are not Git-tracked.
- Customer source/citation rendering is absent: `SOURCE_UI_NOT_IMPLEMENTED`. Real OpenAI and
  DashScope remained off; no language-quality claim, production object-store recovery claim, or PITR
  claim was made. The disposable focused-test database was removed. No PR or merge was created.

State transition:

- P-UAT-02 and P-UAT-02-FIX move to `AWAITING_ACCEPTANCE / EXTERNAL_ACCEPTANCE_PENDING`; Codex does
  not mark either `PASS`.
- P-UAT-03 remains gated on explicit external acceptance. No PR or merge exists.

## P-UAT-03-FIX-1 - Runtime determinism and complaint state-change guard

Started: 2026-09-18

Status: `AWAITING_ACCEPTANCE`

Execution Stage: `EXTERNAL_ACCEPTANCE_PENDING`

- Recovery confirmed accepted main `92a67ecec12d4cae00c31d70cf5a0b6664d393af`, created branch
  `fix/uat03-runtime-side-effects`, and preserved a clean starting worktree. No source changes
  were made before reproducing both defects.
- The red runtime reproduction showed `InteractionSummary.model_dump()` leaving timezone-aware
  `datetime` values in the payload; `CacheManager.set_summaries()` then called plain `json.dumps`
  and raised `TypeError: Object of type datetime is not JSON serializable`. The real baseline
  greeting reached `TURN_ACCEPTED -> RUN_STARTED -> RUN_FAILED` through the same stack.
- The red side-effect reproduction showed P-UAT-03A B4 and D4 consultation turns create direct
  complaint tickets (`3 -> 4` and `4 -> 5`). The current complaint agent had no intent/action or
  explicit-request guard, and the tool opened a session unconditionally.
- The minimum cache repair uses Pydantic Core `to_jsonable_python()` plus sorted-key JSON at the
  shared cache write boundary. Existing JSON reads and model validation remain unchanged. The
  complaint repair uses the existing `IntentCategory`/`IntentAction` values plus explicit raw
  request markers in both `ComplaintAgent` and `ComplaintTool`; no database migration was needed.
- Focused pytest passed `62` selected tests; `1` optional real-LLM unit was deselected because its
  fixture selected OpenAI for a DashScope-only route. The run covered cache, memory, router,
  complaint agent/tool, conversation submission/tools, and chat replay idempotency. Focused Ruff,
  format, and ty passed. The full P-UAT-03A suite was intentionally not run.
- Actual isolated Redis proof stored `2026-09-18T05:06:07Z`/`2026-09-18T05:07:08Z` and restored
  the original typed datetimes. Real Bailian greeting and consultation reached `RUN_COMPLETED`;
  the UAT complaint-ticket count stayed at `5` after the post-fix smoke. Deterministic authorized
  complaint tests and existing runtime idempotency tests passed.
- Real Bailian explicit complaint wording returned `OTHER` on the accepted routing path; one
  wording entered the existing policy loop and reached `RUN_FAILED`, while another completed a
  generic policy response without creating a ticket. This is classified as an out-of-scope
  routing/model-quality failure; no routing, prompt, retrieval, model, or frontend tuning was
  performed.
- No migration, PR, push, or merge was created. External acceptance is required.

## P-UAT-03-FIX-1B - Explicit complaint end-to-end routing

Started: 2026-09-18

Finished: 2026-09-18

Status: `AWAITING_ACCEPTANCE`

Execution Stage: `EXTERNAL_ACCEPTANCE_PENDING`

- Recovery confirmed branch `fix/uat03-runtime-side-effects`, previous head
  `cc02db782b40447353f36965f3ee0b361b4513a1`, accepted main
  `92a67ecec12d4cae00c31d70cf5a0b6664d393af`, and a clean starting worktree. No source was
  changed before the real customer-path reproduction. The exact pre-fix evidence showed the
  existing `router_node -> memory_node -> supervisor_node -> policy_agent -> synthesis_node ->
  evaluator_node -> router_node` recursion topology after a bad/stale intent selected policy.
- A red classifier test proved explicit complaint wording was classified as `COMPLAINT/QUERY`
  rather than the existing state-changing `APPLY` action. A red intent-service test proved a
  stale cached `OTHER` classification was returned before the correct deterministic rule. The
  current baseline cache also contained stale `COMPLAINT/QUERY` entries for all three exact
  complaint forms.
- The minimum fix adds a narrow explicit complaint rule for Chinese and English
  file/submit/create/escalate wording, returns confidence `1.0` for that rule, and adds
  `COMPLAINT` to the existing classifier prompt intent list. The intent service rechecks this
  deterministic rule on cache hits only for explicit complaint actions. No graph limit, general
  route, retrieval, policy prompt, model, or business workflow was changed.
- Focused verification passed `139` tests with `8` optional real-model tests deselected. The
  selected coverage included intent classifier/service, session/cache contamination, router,
  Supervisor, complaint agent/tool authorization, terminal graph execution, FIX-1 cache/memory,
  Conversation Runtime, and replay idempotency. Ruff, Ruff format check, and ty passed.
- Real Bailian mini-suite passed on fresh synthetic threads: greeting `RUN_COMPLETED`; English
  defect consultation `RUN_COMPLETED`, ticket delta `0`; Chinese return-policy consultation
  `RUN_COMPLETED`, ticket delta `0`; exact explicit complaint `RUN_COMPLETED`, route `complaint`,
  ticket delta `1`, ticket `10`; explicit service complaint `RUN_COMPLETED`, route `complaint`,
  ticket delta `1`, ticket `11`. Same-key replay created one ticket total for its authorized
  turn (ticket `12`), with no duplicate.
- No migration, PR, push, or merge was created. The full P-UAT-03A suite was intentionally not
  run. External acceptance is required.

## P-UAT-03-FIX-2 - Knowledge-policy routing and grounded RAG

Started: 2026-09-19

Finished: 2026-09-19

Status: `AWAITING_ACCEPTANCE`

Execution Stage: `EXTERNAL_ACCEPTANCE_PENDING`

- Recovery used the externally accepted FIX-1B head
  `405d7cf6351a2e00a16838e7af53f0e8102331de` on `fix/uat03-runtime-side-effects`; the accepted
  main baseline remains `92a67ecec12d4cae00c31d70cf5a0b6664d393af`. No source was changed before
  reproducing the representative policy-routing failures.
- Real Bailian classifier/service probes reproduced Aurora, Nova, East Harbor, and paraphrase
  policy questions being sent to stale or transaction intents. Direct Tenant A HybridRetriever
  probes retained the expected Aurora, Nova, and East Harbor documents before the fix, proving
  the primary defect was routing/cache precedence rather than Qdrant recall.
- The focused implementation adds an authoritative, narrow rule tier for read-only policy
  semantics and transaction controls, and lets deterministic `POLICY/CONSULT` classification
  supersede only stale intent-cache/session results. Existing router mapping already sent POLICY
  to `policy_agent`; no graph, PolicyAgent, retrieval, reranker, prompt, model, tool, or schema
  change was made.
- Final focused verification passed `141` selected tests with `10` optional real-model tests
  deselected. `uv run ruff check app tests`, `uv run ruff format --check app tests`, and
  `uv run ty check --error-on-warning app tests` passed. The full P-UAT-03A suite was intentionally
  not run.
- The real Bailian ten-case mini-suite completed all ten turns with `RUN_COMPLETED`, correct
  policy routing, expected Tenant A evidence, materially correct known facts `9/9`, and safe
  no-answer behavior. Policy consultations created zero complaint/refund side effects. The
  provider had no terminal failures; embedding timeout warnings were recovered by existing sparse
  fallback, and one transient reranker connection error was recovered by its bounded retry. One
  known answer retained the correct 28-month warranty fact but added an unsupported hypothetical
  date example; this remains outside FIX-2's routing scope.
- The exact disposable database `test_uat03fix2` was verified and removed. No migration, PR, push,
  or merge was created. External acceptance is required; Codex does not mark this task `PASS`.

## P-UAT-03-FIX-3 - Business-tool routing and refund approval boundary

Started: 2026-09-19

Finished: 2026-09-19

Status: `AWAITING_ACCEPTANCE`

Execution Stage: `EXTERNAL_ACCEPTANCE_PENDING`

- Recovery confirmed branch `fix/uat03-runtime-side-effects`, previous head
  `76ac105435236eff3286a787201c5dc46dcd65e1`, accepted main
  `92a67ecec12d4cae00c31d70cf5a0b6664d393af`, and a clean starting worktree. The real Bailian
  customer-path reproductions were completed before source changes: E2 selected `ORDER/QUERY`
  and returned an order card, while E3/F1/F2 also selected `ORDER/QUERY` and created no refund or
  audit records.
- The primary cause was deterministic rule precedence. The concrete-order logistics wording did
  not match the narrow logistics rule, and generic order/SN rules won. The explicit return request
  likewise fell through to the generic `SN\d+` order rule. Router mappings, LogisticsTool,
  OrderService, RefundService, eligibility, risk thresholds, outbox, and approval code were
  already present and were not changed.
- The minimal implementation adds narrow concrete-order Chinese/English logistics and explicit
  refund/return action rules, extracts the existing `order_sn` slot and `REFUND` tertiary action,
  and protects these high-signal deterministic results from stale Redis intent-cache entries.
  A focused cross-user known-order logistics negative test was added. No prompt, model, RAG,
  multi-turn, business-rule, schema, migration, PR, push, or merge change was made.
- Focused verification passed: intent classifier/service `82 passed, 7 skipped`; router,
  supervisor, and logistics agent `21 passed`; LogisticsTool `4 passed`; OrderService refund
  entry/ownership `7 passed`; RefundService `12 passed`; refund tasks/outbox/audit `12 passed`; conversation
  idempotency `2 passed`; FIX-1 summary-cache regression `1 passed`. Ruff check, format check,
  and ty passed for all changed Python files.
- The real Bailian fixed seven-case mini-suite completed all seven turns with `RUN_COMPLETED` and
  no provider failures. Graph logs recorded `LOGISTICS -> logistics`, `ORDER -> order_agent`,
  three `AFTER_SALES -> order_agent` refund paths, `POLICY -> policy_agent`, and
  `COMPLAINT -> complaint`. Tenant A durable deltas were three `PENDING` refund applications,
  two `PENDING` MEDIUM/HIGH audits, two `refund.notify_admin` outbox intents, zero payment
  outbox/receipts, and one explicit complaint ticket. Policy consultation caused no refund,
  audit, or complaint mutation.
- No migration, PR, push, or merge was created. The full P-UAT-03A suite was intentionally not
  run. External acceptance is required; Codex does not mark this task `PASS`.

## P-UAT-03-FIX-4 - Durable multi-turn context and correction handling

Started: 2026-09-19

Finished: 2026-09-19

Status: `AWAITING_ACCEPTANCE`

Execution Stage: `EXTERNAL_ACCEPTANCE_PENDING`

- Recovery confirmed branch `fix/uat03-runtime-side-effects`, previous accepted FIX-3 head
  `79111ba471143ed0dec5d325142fd604e2d51239`, accepted main
  `92a67ecec12d4cae00c31d70cf5a0b6664d393af`, and a clean starting worktree. Real Bailian D1-D4
  reproduction was completed before source changes. Durable cards existed, but the API supplied
  no prior history to intent recognition or `ExecutionRequest`, and each isolated graph state held
  only the current user message.
- The minimal implementation adds trusted bounded history to `TurnSubmission` and
  `ExecutionRequest`, hydrates only completed tenant/user/conversation-owned user/final-assistant
  text pairs from PostgreSQL, excludes failed/partial outputs, and feeds that history to the API
  intent call and the isolated LangGraph run. The current message is appended once by the
  executor. Query-only intent cache use is bypassed only when context is present. Checkpoint/run
  isolation, schema, models, prompts, retrieval, tools, and business rules were not changed.
- New regression coverage proves pair hydration/order, current-message deduplication, failed-turn
  exclusion, same-key replay behavior, checkpoint namespace isolation, context-cache bypass, and
  same-user cross-conversation isolation. Focused non-real-provider verification passed `134` tests
  with `5` optional real-model tests deselected; architecture guard passed `3`; the added runtime
  and security regression passed `6`. Ruff check, Ruff format check, and `ty check --error-on-warning`
  passed for changed files.
- After restarting only the disposable application container to load the current source, the real
  Bailian D1-D4 run completed all turns without provider failures or `RUN_FAILED`, but did not meet
  semantic expectations: D1/D2 initial policy turns were PRODUCT, short follow-ups were OTHER,
  D3/D4 follow-ups were safety-blocked, and the explicit topic-switch control stayed on ORDER/
  product instead of logistics. An explicit complaint control hit `GraphRecursionError`, and the
  explicit refund control stayed on ORDER; these are preserved FIX-1B/FIX-3 routing/runtime issues
  outside FIX-4 and were not changed. No unauthorized complaint, refund, or audit mutation occurred
  in the controls.
- No migration, PR, push, or merge was created. The full P-UAT-03A suite was intentionally not
  run. External acceptance is required; Codex does not mark this task `PASS`.
