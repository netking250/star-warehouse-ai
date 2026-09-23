# P-UAT-02-FIX - Summarization Gateway Non-Streaming Semantics

## Status

- Task: `P-UAT-02-FIX`.
- Status: `AWAITING_ACCEPTANCE`.
- Execution stage: `EXTERNAL_ACCEPTANCE_PENDING`.
- Branch: `fix/knowledge-worker-storage`.
- Accepted head before fix: `dc2e08ec7ce14daf4d07e8cbcfe8b76b763877e7`.
- P-UAT-01: externally reported `PASS_WITH_NOTES`.
- P-UAT-02A-FIX: externally reported `PASS_WITH_NOTES`.
- P-UAT-02: `FAIL` at the chat runtime summarization blocker.

## Accepted evidence

- Five documents uploaded and synchronized into five chunks/five Qdrant points with zero failures.
- Exact, paraphrase, shipping, warranty, distractor, and no-answer retrieval checks passed.
- Tenant A received no Tenant B evidence; the Tenant B control query retrieved Tenant B data.
- The real conversation reached PolicyAgent, HybridRetriever, and ModelGateway with correct Aurora
  evidence before summarization capability selection failed.

## Reproduction target

Use `SessionSummarizer.summarize_thread()` inside the same LangGraph event-stream context as the
real runtime, backed by a `summarization` route whose selected candidate advertises only `chat`.
Capture the effective requested capabilities, candidate, adapter method/attempt count, normalized
exception, and prove the pre-fix failure occurs before provider I/O.

## Root-cause hypotheses

1. LangChain's `BaseChatModel._agenerate_with_cache()` auto-selects `_astream()` during `ainvoke`
   when `astream_events()` installs an inherited streaming callback.
2. ModelFailurePolicy or ModelGateway adds `streaming` unconditionally.
3. SessionSummarizer explicitly requests streaming.

Source inspection currently supports hypothesis 1 and contradicts 2 and 3; the red regression must
prove the behavior before the adapter is changed.

## Frozen scope

- Preserve `ainvoke` as non-streaming gateway execution requiring only its actual capabilities.
- Preserve `astream` as true streaming execution requiring `chat + streaming`.
- Do not change resolver validation, route capabilities, summarization trigger behavior, provider
  configuration, T14 retry/fallback/circuit ownership, or knowledge ingestion/retrieval design.
- Keep real OpenAI and DashScope off. Do not implement structured source UI or real tool calling.

## Verification plan

1. Add and run the failing LangGraph/summarizer regression at the public adapter seam.
2. Apply the minimum adapter-local semantic fix and rerun the red test.
3. Add focused capability-matrix, missing-chat, structured-output, conversation terminal,
   cancellation/timeout, and failure-policy ownership checks.
4. Run scoped Ruff, Ruff format check, ty, gateway tests, summarization tests, and conversation tests.
5. Reuse the existing synthetic stack/corpus where valid to resume only the blocked Aurora chat,
   dedicated cross-tenant completion, re-sync, delete, post-delete chat, and browser evidence.
6. Record exact evidence, commit the focused change, and leave the task at `AWAITING_ACCEPTANCE`.

## Non-goals

No ingestion/retrieval redesign, route capability inflation, resolver bypass, direct provider call,
full backend suite, real-model quality claim, structured citation UI, production object-store
recovery claim, PITR work, PR, or merge.

## Result

- The red reproduction used `SessionSummarizer.summarize_thread()` inside
  `StateGraph.astream_events()` with a `summarization` candidate advertising `chat` only. Public
  `ainvoke()` inherited LangChain's streaming callback, entered `_astream()`, requested
  `chat + streaming`, raised `No candidate for route 'summarization' supports: chat, streaming`, and
  made zero provider attempts.
- Root cause was LangChain's `_agenerate_with_cache()` callback-driven auto-stream selection, not
  `ModelRequest.required_capabilities`, ModelGateway resolution, failure policy, route configuration,
  or the summarizer call site.
- The adapter-local repair overrides public `ainvoke()` to pass `stream=False` into the inherited
  implementation. It preserves LangChain callbacks, tracing, and caching while ensuring the call
  reaches `_agenerate()` and the non-streaming Model Gateway request. Public `astream()` still reaches
  `_astream()` and requires `chat + streaming`.
- Capability tests prove: chat-only `ainvoke` succeeds and requests `{chat}`; chat-only `astream` is
  rejected before provider I/O; streaming-capable `astream` succeeds and requests
  `{chat, streaming}`; a candidate lacking chat remains a configuration error.
- Focused verification passed `95` tests with `1` opt-in real-model test skipped. It covers the full
  Model Gateway suite, actual LangGraph summarization, structured output, durable conversation
  completion, cancellation, global timeout, post-visible timeout, duplicate-terminal prevention,
  and T14 fallback/circuit ownership. Ruff, Ruff format, and ty passed.
- Real run `cbfb389e-cea3-41d7-8124-5bae5c6a7b0e` completed the Aurora question with Document A's
  `AURORA-REFUND-17` present in provider context, one persisted agent card, one `RUN_COMPLETED`, and
  no `RUN_FAILED` or duplicate response. The deterministic answer wording remains outside this gate.
- Default-tenant run `fe54f06b-4b70-47b6-9049-ed84a54d9c79` completed the private-sentinel question
  with zero Tenant B document heading/private sentence in provider context, zero private content in
  the answer, one agent card, and one terminal event. The already accepted focused retrieval probe
  independently returned zero retained Tenant B evidence for Tenant A.
- Re-syncing `east-harbor-shipping.txt` kept its tenant-scoped point count `1 -> 1`, left no duplicate
  or stale point, and retained East Harbor Top-1 at `0.99`. Deleting default-tenant document `4`,
  `orbit-lamp-general.txt`, through the real API removed its DB row, source object, and Qdrant point
  (`1 -> 0`). The deleted document was absent from focused retrieval and provider context; three
  unrelated points remained and Aurora stayed Top-1 at `0.95`.
- The prior `Event loop is closed` warning did not reproduce in the re-sync/app/worker logs and had
  no state or resource impact in this run, so it remains `NON_BLOCKING_DIAGNOSTIC`.
- Browser proof is stored only under
  `C:\Users\11\AppData\Local\Temp\star-warehouse-ai-p-uat-02-fix-20260918-173240`.
  Admin Knowledge visibly shows synchronized Aurora, East Harbor, and Nova documents; customer chat
  visibly shows the Aurora question and completed analysis. The clean capture recorded zero console
  errors, HTTP 4xx, HTTP 5xx, or runtime exceptions.
- Repository inspection found no structured source/citation rendering in the customer UI:
  `SOURCE_UI_NOT_IMPLEMENTED`. Real OpenAI and DashScope remained off. Production object-store
  recovery and PITR were not exercised. The disposable focused-test database was removed.
- No PR or merge was created. External acceptance is required; Codex does not mark this work `PASS`.

## Final closeout (2026-09-23)

Status: PASS_WITH_NOTES. Earlier status and evidence above are preserved as historical observations.
