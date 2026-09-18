# P-UAT-03-FIX-1 - Runtime Determinism and Complaint State-Change Guard

## Status

- Task: `P-UAT-03-FIX-1`.
- Status: `AWAITING_ACCEPTANCE`.
- Execution stage: `EXTERNAL_ACCEPTANCE_PENDING`.
- Branch: `fix/uat03-runtime-side-effects`.
- Accepted base main: `92a67ecec12d4cae00c31d70cf5a0b6664d393af`.
- P-UAT-03A: `FAIL`; this fix owns only the recent-summary cache runtime failure and
  unauthorized `ComplaintTicket` creation.

## Frozen scope

- Repair typed datetime serialization at the shared Redis cache write boundary.
- Require an explicit complaint/file/escalation request plus the existing complaint intent
  semantics before `ComplaintTicket` persistence.
- Preserve the existing runtime idempotency contract for duplicate submissions.
- Do not tune prompts, intent routing, retrieval, models, frontend behavior, or migrations.
- Do not run the full P-UAT-03A suite.

## Reproduction

- `InteractionSummary.model_dump()` produced a dictionary containing timezone-aware
  `datetime` values. `CacheManager.set_summaries()` passed it to plain `json.dumps()`, raising
  `TypeError: Object of type datetime is not JSON serializable` and causing `RUN_FAILED`.
- On the real UAT stack, the pre-fix greeting reached `RUN_FAILED` with the same cache stack.
- P-UAT-03A's B4 and D4 consultation turns increased `ComplaintTicket` count from `3 -> 4` and
  `4 -> 5`, respectively, without an explicit request to file or escalate a complaint.

## Implementation and evidence

- `CacheManager` now converts all cache writes through Pydantic Core's
  `to_jsonable_python()` and deterministic sorted-key JSON. Existing `json.loads()` plus model
  validation reconstructs datetime fields.
- `ComplaintAgent` rejects a routed consultation before tool invocation. `ComplaintTool` repeats
  the same authorization check before opening a database session, and returns explicit
  `created/authorized` state so the agent cannot claim a ticket when persistence did not occur.
- Focused pytest: `62 passed, 1 deselected` (only the optional real-LLM test whose fixture selects
  an unavailable OpenAI route was deselected). Focused Ruff, format, and ty passed.
- Actual isolated Redis round-trip stored ISO UTC strings and reconstructed the original datetime
  values. Greeting and policy consultation completed on the real Bailian app path; the UAT
  `ComplaintTicket` count remained `5` after post-fix consultation and explicit-route attempts.
- The real provider returned `OTHER` for the explicit complaint smoke, so it went to the existing
  policy route; one variant hit the existing LangGraph recursion failure. This is an existing
  routing/model-quality failure and was not changed under this task's frozen scope.
- Deterministic authorized complaint-agent/tool tests and existing runtime idempotency tests pass.

## Remaining gate

The explicit complaint workflow is proven at the deterministic agent/tool seam, but the real
Bailian API smoke did not reach that seam because the accepted baseline's intent/routing behavior
returned `OTHER`. External acceptance must decide whether this out-of-scope product-quality gate
belongs to the next P-UAT-03 FIX stage.

No PR or merge was created.
