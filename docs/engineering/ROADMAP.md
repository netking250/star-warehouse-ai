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
| T15 | Frontend Transport | NOT_STARTED |
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
