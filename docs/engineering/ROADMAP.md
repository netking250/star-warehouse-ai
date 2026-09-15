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
| T15 | Frontend Transport | AWAITING_ACCEPTANCE |
| T16 | Enterprise Console | NOT_STARTED |
| T17 | Observability | NOT_STARTED |
| T18 | CI/CD + Supply Chain | NOT_STARTED |
| T19 | Helm + k3s + AWS Reference | NOT_STARTED |
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
- T14 remains externally accepted `PASS_WITH_NOTES`; T16 remains `NOT_STARTED`.
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

T14 remains `PASS_WITH_NOTES`; T16 remains `NOT_STARTED`. External acceptance is required before
T15 may move to `PASS` or T16 may begin.

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
