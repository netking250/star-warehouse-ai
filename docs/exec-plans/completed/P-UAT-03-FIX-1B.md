# P-UAT-03-FIX-1B - Explicit Complaint End-to-End Routing

## Status

- Task: `P-UAT-03-FIX-1B`.
- Status: `AWAITING_ACCEPTANCE`.
- Execution stage: `EXTERNAL_ACCEPTANCE_PENDING`.
- Branch: `fix/uat03-runtime-side-effects`.
- Previous head: `cc02db782b40447353f36965f3ee0b361b4513a1`.
- Accepted base main: `92a67ecec12d4cae00c31d70cf5a0b6664d393af`.
- P-UAT-03A: `FAIL`; this focused repair owns only explicit complaint routing/runtime recursion.

## Frozen scope

- Make unambiguous complaint/file/submit requests resolve to the existing
  `COMPLAINT` intent and state-changing `APPLY` action.
- Prevent a stale cached intent from overriding that deterministic complaint rule.
- Preserve the FIX-1 persistence-side authorization guard and existing idempotency behavior.
- Do not tune general intent quality, retrieval, policy prompts, models, frontend behavior,
  business workflows, or graph recursion limits.
- Do not run the full P-UAT-03A suite.

## Reproduction and root cause

- The pre-fix complaint rule matched `投诉` as `COMPLAINT/QUERY`, so an explicit request to
  create a ticket did not carry the existing state-changing action.
- The intent service returned cached results before running the classifier. A stale cached
  `OTHER`/non-action result could therefore survive a correct deterministic rule and send the
  graph to the policy path.
- The observed failure topology was the existing retry path:
  `router_node -> memory_node -> supervisor_node -> policy_agent -> synthesis_node ->
  evaluator_node -> router_node`. Repeated low-confidence policy evaluation reached the
  existing LangGraph recursion limit. The fix makes the explicit request deterministic before
  that path is selected; the recursion limit and graph topology were not changed.
- The prior real Bailian reproduction recorded `RUN_FAILED/GraphRecursionError` for one explicit
  wording and a policy/`OTHER` route for another. A Unicode-safe reproduction on the current
  baseline also showed the stale cache as `COMPLAINT/QUERY`; the red service regression proves
  an `OTHER` cache entry would override the rule.

## Implementation and evidence

- Added a narrow explicit complaint rule for Chinese and English file/submit/create/escalate
  wording. It returns `COMPLAINT/APPLY` with confidence `1.0`, making the existing rule path
  authoritative for this unambiguous action only.
- Added `COMPLAINT` to the classifier prompt's existing primary-intent list so the prompt and
  function schema agree for this intent. No other prompt or taxonomy redesign was made.
- On a cache hit, the service rechecks only the deterministic explicit complaint rule and uses it
  instead of a stale cached classification. Other intent cache behavior is unchanged.
- Focused regression coverage includes classifier variants and consultations, LLM-OTHER
  protection, stale cache/session processing, router, supervisor, complaint/tool guard,
  terminal graph execution, FIX-1 cache/memory, Conversation Runtime, and replay idempotency.
- Final focused verification: `139 passed, 8 deselected`; Ruff, Ruff format check, and ty passed.
- Real Bailian mini-suite: greeting completed; English defect consultation completed with ticket
  delta `0`; Chinese return-policy consultation completed with delta `0`; exact explicit complaint
  completed with exactly one ticket (ticket `10`); explicit service complaint completed with
  exactly one ticket (ticket `11`). Same-key replay produced exactly one additional ticket for
  its own authorized turn (ticket `12`). Provider errors and recursion errors were absent.

## Remaining gate

No focused gate remains for this task. External acceptance is required; Codex does not mark the
task `PASS`. No PR was created and no merge was performed.
