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
| T14 | AI Failure Policy | AWAITING_ACCEPTANCE |
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

## Gate rules

- T-INIT through T13 and M01-M02 are accepted `PASS`. T14 is `AWAITING_ACCEPTANCE` on its
  dedicated feature branch and remains pending external acceptance.
- A task in `AWAITING_ACCEPTANCE`, `FAIL`, `NEEDS_EVIDENCE`, or `BLOCKED` is not accepted as a prerequisite for the next task.
- Do not skip a task because an older roadmap claims similar work is complete. Use current code and current verification evidence.
- A task plan starts in `docs/exec-plans/active/Txx.md` and moves to `completed/` only after external acceptance.
- Historical execution records in [`EXECUTION_LOG.md`](EXECUTION_LOG.md) are append-only. Current state is always [`PROJECT_STATE.md`](PROJECT_STATE.md).

## Suggested dependency flow

`T-INIT → T00 → T01 → T02 → T03 → T04 → T05 → T06 → T07 → T08 → T09 → T10 → T11 → T12 → T13 → T14 → T15 → T16 → T17 → T18 → T19 → T20 → T21`

The sequence is the default gate order. A user may issue a documented change request, but any dependency exception must be recorded in `PROJECT_STATE.md` and the active plan before implementation.
