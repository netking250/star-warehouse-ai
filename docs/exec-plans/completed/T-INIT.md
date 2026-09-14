# T-INIT — Persistent Project Memory

## Objective

Create a persistent, Git-tracked execution memory and recovery protocol for all later enterprise-hardening tasks.

## In Scope

- Add the managed protocol section to root `AGENTS.md` without removing existing rules.
- Add `docs/engineering/PROJECT_STATE.md`, `ROADMAP.md`, `DECISIONS.md`, and `EXECUTION_LOG.md`.
- Add the `docs/exec-plans/` lifecycle and the active T-INIT plan.
- Verify paths, state consistency, and whitespace.

## Non-goals

- No business logic, schema, migration, dependency, agent, RAG, memory, Celery, authentication, frontend, Kubernetes, CI/CD, or infrastructure implementation.
- Do not start T00.
- Do not mark T-INIT as `PASS` without external acceptance.

## Architecture Constraints

- Follow the frozen baseline in [`docs/engineering/DECISIONS.md`](../../engineering/DECISIONS.md).
- Preserve the existing root `AGENTS.md` content and historical docs.
- Keep state files Git-tracked and append-only where specified.
- Treat `PROJECT_STATE.md` as current state and `EXECUTION_LOG.md` as history.

## Implementation Plan

1. Inspect repository state, branch, HEAD, AGENTS files, docs, architecture, ADR, and CI.
2. Create the engineering memory documents and execution-plan directories.
3. Add the root managed protocol.
4. Verify required files, links/paths, task statuses, and `git diff --check`.
5. Record evidence and hand off at `AWAITING_ACCEPTANCE`.

## Acceptance Criteria

- Root protocol requires context recovery before modifications and defines START/DURING/FINISH behavior.
- Project state, roadmap, decisions, and execution ledger are present and internally consistent.
- ROADMAP includes T-INIT and every task T00–T21.
- DECISIONS records the frozen architecture directions and append-only change rule.
- Execution ledger contains a T-INIT record.
- No business or infrastructure code changed.
- Whitespace and repository-path verification pass.
- Final state is `T-INIT: AWAITING_ACCEPTANCE`, next task `T00`.

## Verification Commands and Results

- `git diff --check` — PASS.
- Path existence and Markdown target checks — PASS.
- ROADMAP/state consistency checks — PASS.
- Application test suites — NOT RUN; intentionally outside T-INIT scope.

## Current Findings

- Pre-edit worktree was clean.
- Branch was `main`; base HEAD was `bf0d5b9`.
- Existing root and scoped AGENTS files exist; no override file exists.
- Existing documentation has historical/product roadmap and ADR content, but no persistent execution memory system.
- Existing CI includes brand/docs, backend, frontend, Docker smoke, evaluation, monitoring, and performance workflows.

## Blockers and Handoff

- No technical blocker is known.
- External acceptance is the only gate. Keep this plan under `active/` until T-INIT is explicitly accepted.
- On acceptance, move this file to `../completed/T-INIT.md`, update state/roadmap, and begin T00 only.

## T-INIT-FIX Update

- **Objective:** Record the frozen Disaster Recovery decision without changing acceptance status.
- **Decision:** ADR-020 covers Demo automated backups and Restore Test; Production Reference HA and PITR; explicit RPO/RTO; Restore Runbook; recovery verification evidence; and different Demo/Production topology and cost tiers.
- **Files synchronized:** `DECISIONS.md`, `PROJECT_STATE.md`, `ROADMAP.md`, `EXECUTION_LOG.md`, and this active plan.
- **Verification:** ADR/status consistency and `git diff --check` must pass.
- **Result:** T-INIT remains `AWAITING_ACCEPTANCE`; T00 remains `NOT_STARTED`.

## External Acceptance

- **Accepted:** 2026-09-11.
- **Result:** `PASS`.
- **Transition:** This plan moves to `docs/exec-plans/completed/T-INIT.md`; T00 becomes `IN_PROGRESS`.
