# Execution Plans

Execution plans hold task-level scope and evidence without bloating the current-state document.

## Lifecycle

1. At task start, create `active/Txx.md` if the task has no plan.
2. Read the plan during context recovery and update it when findings, blockers, or scope change.
3. Finish implementation with actual verification commands and leave the task status at `AWAITING_ACCEPTANCE`.
4. After an explicit external `PASS` or `PASS_WITH_NOTES`, move the plan to `completed/Txx.md` and update `PROJECT_STATE.md` and `ROADMAP.md`.
5. Never delete completed plans. The execution ledger in [`docs/engineering/EXECUTION_LOG.md`](../engineering/EXECUTION_LOG.md) is also append-only.

Plans should cover:

- Objective.
- In scope and non-goals.
- Architecture constraints and applicable decisions.
- Implementation plan.
- Acceptance criteria.
- Verification commands and real results.
- Current findings, blockers, and handoff notes.

The accepted engineering, UAT, UI, and V1.2 implementation plans are archived
under [`completed/`](completed/), including the superseded failed FIX-4 attempt.
No implementation plan remains active. The documentation-only
PROJECT-CLOSEOUT-01 reconciliation awaits external review; it does not reopen
the accepted product lifecycle.
