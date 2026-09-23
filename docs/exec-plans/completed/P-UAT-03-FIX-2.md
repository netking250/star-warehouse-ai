# P-UAT-03-FIX-2 - Knowledge-Policy Routing and Grounded RAG

## Status

- Task: `P-UAT-03-FIX-2`.
- Status: `AWAITING_ACCEPTANCE`.
- Execution stage: `EXTERNAL_ACCEPTANCE_PENDING`.
- Branch: `fix/uat03-runtime-side-effects`.
- Previous head: `405d7cf6351a2e00a16838e7af53f0e8102331de`.
- Accepted base main: `92a67ecec12d4cae00c31d70cf5a0b6664d393af`.
- Scope: knowledge-policy routing and grounded retrieval only.

## Frozen scope

- Route the tested informational return, warranty, shipping, and dispatch questions to the
  existing `POLICY/CONSULT` path and `policy_agent`.
- Preserve the distinction between read-only policy consultation and order, logistics, refund,
  and complaint actions.
- Preserve FIX-1/FIX-1B cache serialization, complaint authorization, explicit complaint routing,
  and idempotency.
- Do not tune retrieval thresholds, reranking, models, prompts, tool workflows, or multi-turn
  memory. Do not run the full P-UAT-03A suite.

## Reproduction and root cause

- Before the fix, the real Bailian classifier/service probes classified the representative Aurora,
  Nova, and East Harbor policy questions as `AFTER_SALES/QUERY`, `PRODUCT/QUERY`, `ORDER/QUERY`,
  or stale cached transaction intents. The router therefore selected a stateful specialist and
  `PolicyAgent`/RAG was not entered. The non-defect shipping consultation was also vulnerable to
  the generic legacy complaint rule.
- Direct Tenant A `HybridRetriever` probes retained the expected Aurora, Nova, and East Harbor
  documents before the routing change. This falsified Qdrant as the primary cause for the
  representative failures.
- The fix adds a small authoritative rule tier ahead of legacy rules for the tested policy
  semantics and transaction controls. On cache hits, only a deterministic `POLICY/CONSULT` rule
  is allowed to supersede stale cached classification; global intent caching remains enabled.

## Implementation and evidence

- Changed `app/intent/classifier.py` and `app/intent/service.py`, plus focused classifier,
  service, and router tests. No retrieval or PolicyAgent production code changed.
- Focused route/RAG/graph verification passed `141` selected tests with `10` optional real-model
  tests deselected. Final Ruff, format, and ty checks passed.
- The real Bailian ten-case mini-suite completed with `RUN_COMPLETED` for every case, correct
  policy routing, Tenant A evidence, materially correct known facts `9/9`, and a safe no-answer
  fallback. Policy questions created zero complaint/refund side effects. Transaction controls
  remained on their stateful routes. The provider had no terminal failures; embedding timeout
  warnings were recovered by the existing sparse fallback, and one transient reranker connection
  error was recovered by a bounded retry.
- One known answer included an unsupported hypothetical date example while preserving the correct
  28-month warranty fact; this remains an answer-quality limitation outside this narrow routing
  fix and is recorded for later work.

## Verification commands

- Focused pytest: intent classifier/service, router/supervisor, PolicyAgent, retrieval/reranker,
  graph workflow/nodes, excluding `requires_llm`.
- `uv run ruff check app tests`.
- `uv run ruff format --check app tests`.
- `uv run ty check --error-on-warning app tests`.
- Full P-UAT-03A was intentionally not run.

## Remaining gate

Implementation, focused verification, disposable-database cleanup, and the focused commit are
complete. The task is `AWAITING_ACCEPTANCE / EXTERNAL_ACCEPTANCE_PENDING`. Codex does not mark the
task `PASS`. No PR or merge is authorized.

## Final closeout (2026-09-23)

Status: PASS_WITH_NOTES. Earlier status and evidence above are preserved as historical observations.
