# P-UAT-03-FIX-4B - Semantic Follow-up and Routing Repair

## Status

- Task: `P-UAT-03-FIX-4B`.
- Status: `AWAITING_ACCEPTANCE`.
- Execution stage: `EXTERNAL_ACCEPTANCE_PENDING`.
- Branch: `fix/uat03-runtime-side-effects`.
- Previous head: `ac6ccf554f1fd0590b59cda9f88aeea8693686ea`.
- Accepted main: `92a67ecec12d4cae00c31d70cf5a0b6664d393af`.

## Frozen scope

- Preserve FIX-4 durable PostgreSQL history hydration, bounded context, completed-answer filtering,
  idempotency, ownership/isolation, and graph state payloads.
- Preserve FIX-1 through FIX-3 complaint guards, explicit actions, policy/RAG grounding,
  logistics tools, refund approval, and business idempotency.
- Do not change models, retrieval/reranking thresholds, tool workflows, business thresholds,
  durable schema, frontend, or the full P-UAT-03A suite.

## Pre-change reproduction

- Real Bailian customer runtime, fresh UTF-8 conversations, 14 turns, zero provider failures.
- D1: `我的 Aurora Chair 能退吗？` rule result was `OTHER/CONSULT 0.3`; runtime selected
  `AFTER_SALES/order_agent`. The 10-day follow-up repeated the order-number clarification.
- D2: 26- and 30-month follow-ups selected incompatible after-sales/policy actions but did not
  apply the age comparison or correction.
- D3: Monday continuation selected `LOGISTICS/QUERY` without an order number instead of continuing
  East Harbor policy.
- D4: the verified-defect follow-up was `POLICY/CONSULT`, but no new specialist invocation ran and
  the prior 17-day answer was reused.
- Supervisor recorded `All agents completed` on new turns. Redis checkpoint keys proved the root
  graph persisted under the shared conversation thread and `__empty__` namespace despite the
  configured run-specific namespace, allowing stale `sub_answers` to satisfy a new run.
- Router passes `question=current` while `history[-1]` is the same current user message; the API
  pre-classifier correctly receives prior history only.
- Current correctly encoded explicit logistics, refund, and complaint controls pass their accepted
  routes. Earlier failed controls persisted `????` instead of the requested Chinese text and are
  retained only as test-harness evidence, not product-rule input.

## Ranked hypotheses

1. Effective checkpoint isolation requires a run-specific root thread identity because LangGraph
   reserves the root namespace as empty.
2. A narrow contextual policy resolver must run after authoritative current-turn rules and before
   topic-switch reset.
3. Intent consumers must receive prior history while Policy/RAG retains full current history.
4. Strict benign follow-up forms need deterministic safety treatment after hard security checks.
5. Query-only cache is not primary because contextual calls already bypass it.

## TDD plan

1. Red/green: actual checkpoint identity differs per run while semantic state thread remains the
   durable conversation ID.
2. Red/green: strip exactly one trailing duplicate current user message at the intent boundary.
3. Red/green: first-turn Aurora policy and contextual D1-D4 continuation/correction resolve to
   `POLICY/CONSULT`; explicit logistics/refund/complaint continue to win.
4. Red/green: benign bounded follow-ups are safe; injection/system-prompt/credential probes remain
   blocked.
5. Focused graph, side-effect, isolation, static, and real Bailian verification.

## Implemented repair

- Use a run-specific root checkpoint thread identity while preserving the durable conversation ID
  in `AgentState` and the PostgreSQL conversation contract.
- Remove exactly one trailing duplicate current user message from intent context; Policy/RAG still
  receives the complete bounded conversation history.
- Preserve explicit current logistics/refund/complaint and policy semantics ahead of contextual
  continuation and stochastic classification.
- Resolve narrow policy duration, correction, and weekday follow-ups against the latest compatible
  same-conversation policy question before model rewriting.
- Keep hard injection/credential checks authoritative, then recognize only bounded benign commerce
  follow-up forms as safe.
- Exclude unrelated cross-interaction memory from grounded PolicyAgent answer generation; durable
  conversation history and retrieved tenant knowledge remain the reasoning sources.

## Verification

- Broad focused regression: `483 passed, 17 deselected`.
- Post-fix impacted regression: `310 passed, 14 deselected`.
- Ruff check: passed.
- Ruff format check: passed (`475 files already formatted`).
- Ty: passed with warnings treated as errors.
- Final real Bailian suite: `17/17 RUN_COMPLETED`, `0 RUN_FAILED`, `0` recursion,
  `0` terminal provider failures.
- D1-D4: `4/4` passed; D2 correction uses 30 months and supersedes 26 months.
- Explicit topic switch: `LOGISTICS -> logistics`, real tracking output returned.
- Explicit refund: `AFTER_SALES -> order_agent`; existing single pending application was reported
  honestly and no duplicate was created.
- Explicit complaint: `COMPLAINT -> complaint`; exactly one new ticket (`18`) and no recursion.
- Latest policy conversations created zero complaint tickets, refunds, or audits.
- No-answer did not invent a discount; prompt injection disclosed no prompt or secret.
- Full P-UAT-03A was not run. No migration, PR, push, or merge was created.

## Final closeout (2026-09-23)

Status: PASS. Earlier status and evidence above are preserved as historical observations.
