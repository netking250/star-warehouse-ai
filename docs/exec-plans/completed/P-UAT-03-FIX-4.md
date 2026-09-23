# P-UAT-03-FIX-4 - Durable Multi-Turn Context and Correction Handling

## Status

- Task: `P-UAT-03-FIX-4`.
- Status: `AWAITING_ACCEPTANCE`.
- Execution stage: `EXTERNAL_ACCEPTANCE_PENDING`.
- Branch: `fix/uat03-runtime-side-effects`.
- Previous accepted head: `79111ba471143ed0dec5d325142fd604e2d51239`.
- Accepted main: `92a67ecec12d4cae00c31d70cf5a0b6664d393af`.
- Scope: durable bounded same-conversation history, correction handling, context-sensitive intent
  classification, topic switching, retry/run isolation, and tenant/user isolation regressions.

## Frozen scope

- Preserve FIX-1 through FIX-3 runtime, complaint, policy/RAG, logistics, refund, approval, and
  ownership behavior.
- Do not tune general answer style, retrieval thresholds, reranking, models, tool business logic,
  refund thresholds, complaint semantics, or frontend behavior.
- Do not reuse mutable LangGraph state across runs and do not run the full P-UAT-03A suite.

## Reproduction

Completed through the real customer API/runtime with real Bailian before source changes:

- D1: Aurora first-turn context was not available to the short age/shipping follow-ups; the age
  turn was cancelled and the later policy answer had to rediscover context.
- D2: `我买了26个月。` and `刚才说错了，是30个月。` were both classified as `OTHER` and
  produced generic responses.
- D3: `East Harbor 的订单通常多久出库？` followed by `那如果是周一确认呢？` retained a
  generic three-business-day answer but the follow-up was classified as `ORDER`.
- D4: the verified-defect follow-up returned the original 17-day answer instead of the defect
  shipping policy.

Durable MessageCards for completed turns were present in PostgreSQL. The API passed
`conversation_history=None` to the pre-execution intent service, `ExecutionRequest` had no
history field, and `LangGraphConversationExecutor` initialized `AgentState.history` with only
the current user message. The existing run-specific checkpoint namespace was left unchanged.

## Hypotheses to verify

1. The execution contract drops durable history before LangGraph initialization.
2. The API-side intent recognition has the same missing-history boundary.
3. Query-only intent caching can reuse a context-free result for a context-dependent follow-up.
4. Redis clarification/session state may amplify the failure but is not the authoritative history
   source.
5. Checkpoint reuse is not the intended fix; run isolation must remain per run.

## Implementation plan

- Add the smallest typed history field at the conversation execution boundary.
- Hydrate only tenant/user-owned completed turn pairs from PostgreSQL before appending the current
  message; exclude partial/failed outputs and bound the result using existing history budget
  conventions.
- Feed the same trusted normalized history to API intent recognition and the LangGraph executor.
- Bypass or scope only context-dependent intent cache use; retain cache behavior for standalone
  queries.
- Add focused red/green tests for history order, one current message, failed-turn exclusion,
  idempotent replay, correction, topic switch, isolation, and run/checkpoint separation.

## Implementation

- `TurnSubmission` and `ExecutionRequest` now carry a typed tuple of normalized prior messages.
- `ConversationRuntime` hydrates only completed, tenant/user/conversation-owned turns that have a
  sent final text assistant card. Failed/partial outputs are excluded and the existing history
  token budget bounds the result while retaining complete edge pairs.
- The API pre-execution intent call and isolated LangGraph initial state receive the same trusted
  prior history; the current user message is appended exactly once by the executor.
- Intent result cache reads/writes remain available for standalone queries but are bypassed for
  context-dependent requests.
- No checkpoint namespace, schema, model, prompt, retrieval, tool, or business-rule changes were
  made.

## Verification record

- Pre-fix real Bailian D1-D4 reproduction completed; the API/executor history-loss boundary and
  query-only contextual-cache defect were reproduced before implementation.
- New regression tests passed for completed-pair hydration, failed-turn exclusion, idempotent
  replay, current-message deduplication, run-isolated checkpoint namespace, context-cache bypass,
  and same-user cross-conversation isolation.
- Focused non-real-provider suite: `134 passed, 5 deselected`; architecture guard: `3 passed`;
  added runtime/security regression: `6 passed`.
- Ruff check, Ruff format check, and `ty check --error-on-warning` passed for all changed source
  and test files.
- Post-restart real Bailian D1-D4 and topic-switch runs completed with zero provider failures and
  zero RUN_FAILED in D1-D4, but did not satisfy the semantic acceptance cases: PRODUCT/OTHER
  initial/follow-up routing, safety filtering, and logistics topic switching remained. The
  explicit complaint control hit GraphRecursionError and the refund control remained ORDER; no
  unauthorized mutation occurred. These are outside FIX-4 and were not changed.
- Temporary test database and container test copies are disposable verification artifacts and are
  not part of the repository changes.

The implementation is `AWAITING_ACCEPTANCE / EXTERNAL_ACCEPTANCE_PENDING`; Codex does not mark
this task PASS.

## Final closeout (2026-09-23)

Status: FAIL; superseded by P-UAT-03-FIX-4B. Earlier status and evidence above are preserved as historical observations.
