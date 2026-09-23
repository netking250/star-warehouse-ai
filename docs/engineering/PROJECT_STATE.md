---
schema_version: 1
project: Star Warehouse AI
phase: V1_2_PROJECT_CONSOLIDATION
current_task: V1.2-BOOTSTRAP-01
current_status: AWAITING_ACCEPTANCE
execution_stage: EXTERNAL_ACCEPTANCE_PENDING
last_accepted_task: UI-04
next_task: V1.2-BOOTSTRAP-01 external acceptance
acceptance_owner: external
maintenance_task: M02
maintenance_status: PASS
---

# V1.2-BOOTSTRAP-01 Current State

CR-PROJECT-02 establishes the V1.2 project-bootstrap and documentation-consolidation baseline on
`chore/v1.2-bootstrap-docs` from the externally accepted UI-04 head
`edfd5577b9ca9ccc3ef6c5ea20b971b1e4c6727e`. The task is
`AWAITING_ACCEPTANCE / EXTERNAL_ACCEPTANCE_PENDING`; only external review may mark it accepted.

`./start_docker.sh` is now the one full-Docker local workflow. It isolates the requested Compose
project explicitly, starts and health-checks infrastructure, applies the single Alembic head,
provisions and verifies NO BYPASSRLS runtime/maintenance roles, runs the production-guarded
canonical bootstrap, starts API/workers/scheduler/outbox, and runs persisted-stack verification.
The environment-driven local/UAT dataset is idempotent and uses current tenancy, auth, storage,
knowledge-ingestion, Qdrant, outbox, and Celery paths; no password is stored or logged by Python.

Disposable fresh-state acceptance on `star-warehouse-v12-accept` reached head `f0a1b2c3d4e5`,
created 2 users/memberships, 4 orders, 1 refund, 1 approval/audit, 1 complaint, 8 agent configs, 11
routing rules, 3 knowledge documents, 7 non-zero tenant-filtered knowledge points, and 5 product
points. Customer/admin login, session restoration/logout, admin capability denial for the customer,
cross-tenant/cross-user isolation, known-source retrieval, Redis connectivity, and one
outbox-to-Celery receipt passed. A second bootstrap retained identical counts, and an application
restart without deleting volumes retained the relational records and vector indexes.

Focused verification passed 140 backend tests, 63 frontend unit tests, the production frontend
build, and 14 Playwright tests. Ruff format/check, ty, project identity/document links, the single
Alembic head, and the pinned gitleaks scan pass. The accepted UI components and visual behavior are
unchanged; only the Vite development proxy gained a configurable target for non-default API ports.

The active plan is
[`docs/exec-plans/active/V1.2-BOOTSTRAP-01.md`](../exec-plans/active/V1.2-BOOTSTRAP-01.md).

# UI-04 Accepted State

UI-03 was externally accepted `PASS_WITH_NOTES` at
`e92a24d551b10c3268524776f4e6261661fb65e5`. UI-04 is externally accepted at
`edfd5577b9ca9ccc3ef6c5ea20b971b1e4c6727e` on `feat/ui-v1.1-enterprise-visual`.

The final audit found and corrected two concrete accessibility defects: Light-theme semantic status
text did not consistently meet WCAG AA contrast, and the custom Admin/Customer mobile drawers did
not provide modal focus management, Escape close, or focus return. The shared Sheet primitive now
owns both drawers, and a token-level regression test covers critical Light/Dark contrast pairs.

Clean install, Prettier, ESLint, 16 unit files / 63 tests, the 1930-module production build, and all
14 Playwright tests pass. The final visual matrix covers every Admin route at 1440, 1280, and 1024,
the Customer experience at 1440, 1280, 1024, 390, and 360, both themes, opening, responsive drawers,
and the accepted functional smoke paths. Visual suites report zero console errors, page errors, and
unexpected HTTP 4xx/5xx. The required ignored evidence and reviewed contact sheet are under
`frontend/test-results/ui-v1.1-final/`.

No unsupported claim, dead active control, horizontal overflow, runtime dependency, backend,
migration, workflow, provider/model, API/auth contract, Agent/RAG, or business-behavior change was
introduced. No PR or merge was created. The completed plan is
[`docs/exec-plans/completed/UI-04.md`](../exec-plans/completed/UI-04.md).

# UI-03 Accepted State

UI-02 was externally accepted `PASS_WITH_NOTES` at
`d1500077432fd6dab1719a027298fb5973b0f146`. UI-03 is externally accepted
`PASS_WITH_NOTES` at `e92a24d551b10c3268524776f4e6261661fb65e5` on the same
`feat/ui-v1.1-enterprise-visual` integration branch. Its scope is limited to the Customer login,
authenticated chat shell, conversation presentation, feedback, notification, and responsive visual
experience on the accepted UI-01 foundation.

The Customer login, non-blank session initialization, navigation, welcome state, message hierarchy,
streaming presentation, composer, feedback, notifications, and mobile drawer now use one calm,
premium conversational language. Unsupported availability, latency, traceability, encryption,
VIP, health, and answer-safety claims were removed. Real session identity and WebSocket connection
state are shown where available; unfinished attachment and inert help controls are absent.

Authentication, cookie session, CSRF, SSE, WebSocket, thread identity, cancellation, feedback API,
tenant boundaries, Agent/RAG behavior, and all business workflows remain unchanged. Clean install,
Prettier, ESLint, 15 unit files / 62 tests, the 1929-module production build, and all 12 Playwright
tests pass. The Customer matrix covers Light/Dark login, empty chat, active/long conversation,
expanded feedback, 1280/1024 layouts, and 390/360px mobile states without console errors,
unexpected HTTP 4xx/5xx, or horizontal overflow. No runtime dependency, backend, PR, or merge was
introduced. The completed plan is
[`docs/exec-plans/completed/UI-03.md`](../exec-plans/completed/UI-03.md).

# UI-02 Accepted State

UI-01 was externally accepted `PASS_WITH_NOTES` at
`5c70565db2985fa943314a3f69d72948ec65dee8`. UI-02 is externally accepted
`PASS_WITH_NOTES` at `d1500077432fd6dab1719a027298fb5973b0f146` on the same
`feat/ui-v1.1-enterprise-visual` integration branch. All eight active Admin routes now use one
operational PageHeader, metric, status, panel, filter, table, and state language on the accepted
Light/Dark foundation. The temporary UI-01 legacy Admin theme bridge is removed.

Clean install, Prettier, ESLint, 58 unit tests, production build, and all 9 Playwright tests pass.
The UI-02 visual test reviewed all eight routes in Light and Dark at 1440px plus Overview,
Operations, and Knowledge at 1024px; it reports no browser console errors or unexpected HTTP
4xx/5xx. Screenshots remain in ignored Playwright output. No API, authorization, session, tenant,
Agent/RAG, backend, business behavior, runtime dependency, customer redesign, fake data, PR, or
merge was introduced.

The completed plan is
[`docs/exec-plans/completed/UI-02.md`](../exec-plans/completed/UI-02.md).

# UI-01 Accepted State

CR-UI-01 establishes the approved `V1.1 / FROZEN — Enterprise Visual Experience Upgrade` baseline.
UI-01 is externally accepted `PASS_WITH_NOTES` on
`feat/ui-v1.1-enterprise-visual`, based on protected main
`0a502933dd3502c97bfff72f66bad89a84735d08`.

The implementation adds one shared semantic light/dark token system, saved-preference and system
theme resolution before first paint, theme controls, a reusable Star + data-grid + AI-core mark,
CSS-only ambient effects, and a deterministic session-scoped opening experience with a reduced-
motion path. Admin and Customer consume the same visual foundation while retaining their existing
routes, authentication, CSRF, SSE, WebSocket, API, permissions, and business behavior. No runtime
dependency, backend change, migration, or fake product data was added.

Focused theme/opening tests, the full frontend unit suite, lint, format, production build, and
Playwright Customer/Admin smoke pass. Browser screenshots cover both themes and the opening frame;
they remain under ignored Playwright output only. Subsequent V1.1 task state is recorded above.

# P-UAT-03-PR-FIX Current State

P-UAT-03-PR-FIX is `AWAITING_ACCEPTANCE / EXTERNAL_ACCEPTANCE_PENDING` on
`fix/uat03-runtime-side-effects` from PR #13
head `98e64fb6e6a385105874be610be8a962ae2bd7ee`. P-UAT-03A-FINAL-RETEST is externally reported
`PASS`; this repair must preserve that accepted product-quality result.

Hosted PR evidence identifies two isolated blockers: the cross-user refund test asserts that the
entire shared `refund_applications` table is empty even though earlier tests may legitimately leave
unrelated rows, and the application image resolves AnyIO `4.13.0`, which is affected by
CVE-2026-63374 and fixed in `4.14.2`. The repair scope is limited to an order-scoped test assertion,
a deterministic polluted-state regression, the narrowest reproducible AnyIO dependency update,
and execution evidence. Production product, authorization, tenant/RLS, AI, prompt, frontend,
refund, approval, and workflow behavior must remain unchanged.

The focused repair now creates a deterministic unrelated refund inside the cross-user regression,
queries only the protected target order and requester after the rejected attempt, and proves that
the unrelated row remains. The production `OrderService` is unchanged. `uv lock --upgrade-package
anyio` changed only AnyIO from `4.13.0` to `4.14.2`; `pyproject.toml` and all other dependencies are
unchanged. Lock check, frozen sync, installed-version inspection, the target test, the 27-test
order/refund suite, Ruff, format, and ty pass.

The CI-shaped image builds with AnyIO `4.14.2`, imports the application as the non-root user, and
passes `/health` on the existing disposable UAT network. The repository-pinned Trivy policy reports
`critical=0`, `high=81`, `high_with_fix=37`, with CVE-2026-63374 absent and no suppression. One
bounded real DashScope/Bailian `qwen-plus` request returned the requested connectivity sentinel.
The single focused commit, normal push, and new-head hosted PR checks remain the external acceptance
boundary; PR #13 must remain open and unmerged.

The active plan is
[`docs/exec-plans/active/P-UAT-03-PR-FIX.md`](../exec-plans/active/P-UAT-03-PR-FIX.md).

# P-UAT-03-FINAL-FIX Current State

P-UAT-03-FINAL-FIX is `AWAITING_ACCEPTANCE / EXTERNAL_ACCEPTANCE_PENDING` on
`fix/uat03-runtime-side-effects` from the accepted local head
`49a97ffb7b5b0c04f8db6f8a3f9cf9128fb1573d`. It owns only the eight failures preserved by
P-UAT-03A-RETEST: B3, C4, D2, D4, E2, E4, F1, and F2.

The final focused repair adds only narrow informational dispatch/repair-fee and explicit refund
wording, contextual defect-policy resolution, confirmed-facts-only complaint copy, and bounded
embedding failure reuse. One shared embedding adapter now coalesces duplicate same-query work and
prevents memory and retrieval from repeatedly paying the same known provider timeout. The 45-second
application SSE deadline, provider deadlines, RAG thresholds, Self-RAG, model routes, authorization,
RLS, refund thresholds, and approval boundary are unchanged.

The disposable UAT preflight now fails before scored provider calls unless SN649201-SN649203 all
match the single benchmark identity. Evidence confirms `tenant-a` user `2` owns all three orders.
Focused real Bailian proof completed all eight original failed scenarios with durable
`RUN_COMPLETED`, zero `RUN_FAILED`, zero missing terminal events, and the required grounded/tool
answers. F1/F2 created exactly one PENDING refund each, MEDIUM/HIGH PENDING audits, and one
`refund.notify_admin` intent each; no payment execution or completed refund occurred. E4 created
one ticket and made no SLA or outcome promise. The requested control matrix also completed safely.

Focused verification passed `223` tests with `10` optional real-model tests deselected. Ruff check,
Ruff format check, and ty passed. Tenant-aware browser-session login and the Customer UI knowledge,
no-answer, D2 correction, logistics, refund-idempotency, and complaint paths were manually verified;
streaming terminated without duplicate/truncated text or application 4xx/5xx. Screenshots are kept
only under the OS temporary UAT artifact directory. The final 30-case retest was not run. No PR,
push, merge, migration, or production authentication change was made.

The active plan is
[`docs/exec-plans/active/P-UAT-03-FINAL-FIX.md`](../exec-plans/active/P-UAT-03-FINAL-FIX.md).

# P-UAT-03-FIX-4B Current State

P-UAT-03-FIX-4B is `AWAITING_ACCEPTANCE / EXTERNAL_ACCEPTANCE_PENDING` on
`fix/uat03-runtime-side-effects` from head
`ac6ccf554f1fd0590b59cda9f88aeea8693686ea`. It preserves FIX-4's PostgreSQL-authoritative
bounded history transport and owns only semantic follow-up resolution, benign-follow-up safety,
explicit-current-intent precedence, and a proven run-checkpoint isolation defect.

The pre-change real Bailian reproduction used fresh UTF-8 conversations. D1 initially selected
`AFTER_SALES/order_agent`; D2/D3 follow-ups selected incompatible transaction domains; D4 retained
the prior 17-day answer rather than answering verified-defect shipping. Two turns skipped the
specialist because Supervisor saw an old same-iteration `sub_answers` entry and reported `All
agents completed`. Redis evidence showed root checkpoints persisted under the conversation
thread's `__empty__` namespace even though the executor supplied a run-specific `checkpoint_ns`,
so prior graph state could be resumed across isolated durable runs.

The minimal repair gives each graph run a run-specific root thread identity while retaining the
durable conversation ID in semantic state, strips the trailing current message only at the intent
boundary, restores narrow authoritative policy/action precedence, and resolves bounded duration,
correction, and weekday follow-ups before stochastic rewriting. Hard security checks still run
before the narrow benign-follow-up safety exemption. Policy generation uses canonical knowledge
evidence and same-conversation contextualization without injecting unrelated cross-interaction
memory.

Final focused verification passed `483` broad selected regressions and `310` post-fix impacted
regressions, with optional real-model tests deselected. Ruff check, Ruff format check, and
`ty check --error-on-warning` passed. The final real Bailian suite completed `17/17` turns with
`RUN_COMPLETED`: D1-D4, correction, explicit topic switch, refund, complaint, logistics,
no-answer, and prompt-injection controls all passed. Graph logs showed D1-D4 as
`POLICY -> policy_agent`, the explicit topic switch as `LOGISTICS -> logistics`, refund as
`AFTER_SALES -> order_agent`, and complaint as `COMPLAINT -> complaint`. Only the explicit
complaint created a new ticket; policy conversations created zero complaints, refunds, or audits.
No recursion, terminal provider error, migration, PR, push, merge, or full P-UAT-03A run occurred.

The active plan is
[`docs/exec-plans/active/P-UAT-03-FIX-4B.md`](../exec-plans/active/P-UAT-03-FIX-4B.md).

# P-UAT-03-FIX-4 Current State

P-UAT-03-FIX-4 is `AWAITING_ACCEPTANCE / EXTERNAL_ACCEPTANCE_PENDING` on
`fix/uat03-runtime-side-effects`, based on the externally accepted FIX-3 head
`79111ba471143ed0dec5d325142fd604e2d51239`. This focused repair owns only durable same-
conversation multi-turn history hydration, correction handling, context-sensitive intent
classification, and the related topic/isolation regressions. It must preserve run-isolated
checkpoints, tenant/user ownership, and all accepted FIX-1 through FIX-3 behavior.

The required real Bailian D1-D4 reproduction is complete. Durable user/assistant MessageCards
exist for completed prior turns, but the API passes `conversation_history=None` before intent
recognition and `ExecutionRequest` has no history field; the LangGraph executor initializes each
run with only the current user message. D1-D4 therefore show lost or misapplied context. The
exact D3 baseline is `East Harbor 的订单通常多久出库？` followed by `那如果是周一确认呢？`.
The confirmed loss boundary was the API/executor contract: durable records existed, but the API
supplied no history to pre-execution intent recognition and each isolated LangGraph run
initialized history with only the current user message. The implementation now hydrates bounded
completed user/assistant pairs from tenant/user/conversation-scoped PostgreSQL records, excludes
failed/partial runs, passes the trusted history through `TurnSubmission` and `ExecutionRequest`,
and preserves the run-specific checkpoint namespace. Context-dependent intent recognition no
longer reads or writes the query-only cache. Focused deterministic tests and static checks pass.

The post-restart real Bailian mini-suite had zero provider errors and zero RUN_FAILED in D1-D4,
but retained pre-existing model/safety/routing failures: D1/D2 initial policy turns were routed
to PRODUCT, short follow-ups were OTHER, D3/D4 follow-ups were safety-blocked, and the explicit
topic switch did not reach the logistics route. The explicit complaint regression control also
hit GraphRecursionError and the refund control remained on ORDER; neither was changed because
tool/complaint/graph routing is outside FIX-4. No unauthorized refund, audit, or complaint
mutation occurred in these controls.

The active plan is
[`docs/exec-plans/active/P-UAT-03-FIX-4.md`](../exec-plans/active/P-UAT-03-FIX-4.md).

# P-UAT-03-FIX-3 Current State

P-UAT-03-FIX-3 is `AWAITING_ACCEPTANCE / EXTERNAL_ACCEPTANCE_PENDING` on
`fix/uat03-runtime-side-effects`, based on the externally accepted FIX-2 head
`76ac105435236eff3286a787201c5dc46dcd65e1`. This focused repair owns only real logistics-tool
routing, explicit refund application flow, risk audit creation, approval boundary, and same-key
idempotency. It preserves policy/RAG routing, complaint guards, memory/cache serialization, and
no-answer safety. Multi-turn memory and general response style remain out of scope.

The required E2/E3/F1/F2 red reproductions were completed before source changes. The minimal fix
adds deterministic concrete-order logistics/refund rules, extracts the existing order slot and
refund tertiary action, and prevents stale intent-cache results from overriding those high-signal
routes. No router, agent, tool, service, eligibility, risk threshold, approval, prompt, model, RAG,
or schema implementation was changed. The real Bailian seven-case mini-suite and focused tests
passed; exact database/outbox/payment evidence is recorded in the active plan.

The active plan is [`docs/exec-plans/active/P-UAT-03-FIX-3.md`](../exec-plans/active/P-UAT-03-FIX-3.md).

# P-UAT-03-FIX-2 Current State

P-UAT-03-FIX-2 is `AWAITING_ACCEPTANCE / EXTERNAL_ACCEPTANCE_PENDING` on
`fix/uat03-runtime-side-effects`, based on
accepted main `92a67ecec12d4cae00c31d70cf5a0b6664d393af` and the accepted FIX-1B head
`405d7cf6351a2e00a16838e7af53f0e8102331de`. This focused repair owns only informational
knowledge-policy routing and grounded PolicyAgent retrieval. It preserves the FIX-1 cache and
complaint state-change repairs and does not repair tool workflows or multi-turn memory.

The pre-fix real Bailian probes showed Aurora, Nova, and East Harbor policy questions resolving to
stale or transaction intents before PolicyAgent; direct Tenant A HybridRetriever probes retained
the expected documents, so the primary defect was routing/cache precedence. The implementation
adds narrow authoritative policy/transaction rules and protects deterministic read-only policy
classification from stale intent-cache/session results. No retrieval threshold, model, prompt,
graph, tool, or schema change was made. Focused tests, static checks, and the real Bailian
mini-suite are recorded in the active plan. P-UAT-03-FIX-1 and P-UAT-03-FIX-1B are externally
accepted prerequisites for this focused stage.

The active plan is [`docs/exec-plans/active/P-UAT-03-FIX-2.md`](../exec-plans/active/P-UAT-03-FIX-2.md).

# P-UAT-03-FIX-1B Current State

P-UAT-03-FIX-1B is externally accepted `PASS` on
`fix/uat03-runtime-side-effects`, based on accepted main
`92a67ecec12d4cae00c31d70cf5a0b6664d393af`. It repairs only explicit complaint end-to-end
routing: an unambiguous file/submit/create request now uses the existing `COMPLAINT/APPLY`
contract, and a stale intent cache cannot override that deterministic rule. The FIX-1
runtime-serialization repair and persistence-side complaint authorization guard remain intact.

The pre-fix failure was traced to the existing `router_node -> memory_node -> supervisor_node ->
policy_agent -> synthesis_node -> evaluator_node -> router_node` retry path after a stale or
misclassified intent selected `policy_agent`; repeated low-confidence evaluation reached the
existing LangGraph recursion limit. No graph recursion limit or general retry behavior changed.
Focused deterministic verification passed `139` tests with `8` optional real-model tests
deselected. The real Bailian five-case mini-suite completed all runs: both explicit complaint
forms entered `complaint` and each created exactly one ticket, while the two consultation forms
created none. Same-key replay created no duplicate ticket.

No general intent/RAG/prompt/model/frontend tuning, migration, PR, or merge was performed. The
completed plan is [`docs/exec-plans/completed/P-UAT-03-FIX-1B.md`](../exec-plans/completed/P-UAT-03-FIX-1B.md).
External acceptance is required before any next UAT fix stage.

# Historical Prior Objective

P-UAT-02-FIX is `AWAITING_ACCEPTANCE / EXTERNAL_ACCEPTANCE_PENDING` on
`fix/knowledge-worker-storage`, based on accepted head
`dc2e08ec7ce14daf4d07e8cbcfe8b76b763877e7`. The pre-fix LangGraph event-stream reproduction proved
that LangChain auto-selected `GatewayChatModel._astream()` for a public `ainvoke()` because an
inherited streaming callback was present, causing the chat-only `summarization` route to request
`chat + streaming` and fail before provider I/O. `GatewayChatModel.ainvoke()` now explicitly pins
the public non-streaming semantic before delegating to LangChain; true `astream()` continues to
require streaming. Resolver, route configuration, summarization, and T14 failure-policy ownership
did not change.

Focused verification passed: `95` focused tests passed and `1` opt-in real-model test skipped across
Model Gateway, summarization, conversation runtime, cancellation/timeout, structured output, and
T14 failure policy; scoped Ruff, Ruff format, and ty passed. The isolated real Aurora chat reached
`COMPLETED`, persisted one agent message, emitted one `RUN_COMPLETED` and no `RUN_FAILED`, and the
provider log contained `AURORA-REFUND-17`. The dedicated default-tenant private-sentinel chat
completed with no Tenant B document heading/private sentence in provider context or answer. East
Harbor re-sync stayed at one point and remained Top-1. Deleting Orbit document `4` removed its DB
row, source object, and tenant-scoped point; it did not reappear in retrieval or post-delete chat
context while Aurora remained Top-1. Browser proof shows the synchronized admin list and a completed
customer chat with zero console errors or HTTP 4xx/5xx in the clean capture. Screenshots are OS-temp
only. The active plan is
[`docs/exec-plans/active/P-UAT-02-FIX.md`](../exec-plans/active/P-UAT-02-FIX.md).

Recovery confirmed branch `fix/knowledge-worker-storage`, accepted head
`dc2e08ec7ce14daf4d07e8cbcfe8b76b763877e7`, and a clean worktree before task-state documentation.
No PR or merge is authorized. Real OpenAI and DashScope calls remain off.

P-UAT-02A-FIX is `AWAITING_ACCEPTANCE / EXTERNAL_ACCEPTANCE_PENDING` on
`fix/knowledge-worker-storage`, based on
protected `origin/main` at `5d84b034513e79557c6ad9ce9fb819832034352f`. P-UAT-01 is externally
reported `PASS_WITH_NOTES`. The focused post-merge repair owns only the local/demo knowledge
upload -> shared source object -> tenant worker -> parse/chunk -> Qdrant path. It must preserve
the production S3-compatible object-storage target as not currently active and must not claim
Docker named-volume durability as a production object-store solution. The active plan is
[`docs/exec-plans/completed/P-UAT-02A-FIX.md`](../exec-plans/completed/P-UAT-02A-FIX.md).

The pre-fix real-stack reproduction uploaded synthetic document `3` and persisted reference
`uploads/knowledge/tenant/default/128cfb2edc6340798f54b78077163432.txt`. The API container read
the 91-byte sentinel object, while the tenant worker at the same `/app` working directory reported
`FileNotFoundError`; neither container had a shared uploads mount. The document reached explicit
`failed` state after bounded retries. Root-cause classification is `LOCAL_VOLUME_NOT_SHARED` with
an accompanying `STORAGE_ADAPTER_CONTRACT_BUG`: the worker bypasses a canonical object-store
contract and opens the database value as a process-local path.

The focused repair now persists `tenant/{tenant_id}/{object}` keys, resolves bytes through the
canonical tenant-aware storage Port, and gives API, tenant worker, and maintenance worker the same
non-root-writable local/demo named volume and root. The task payload remains document identity only.
Missing source objects enter bounded retry and terminal `failed` state; delete and retention remove
both source bytes and tenant-scoped derived vectors. A fresh isolated Compose proof uploaded
`STAR_WAREHOUSE_KB_UAT_SENTINEL_9274`: document `1`, task
`40068d5f-c0da-4ccb-acbd-8f064c5168b8`, final `SUCCESS`, one chunk, one Qdrant point with
`tenant_id=default`, and identical API/worker source SHA-256
`d9403452220caa77f389353062ce9548a32701ba52ec9519b0516811540ff109`. Re-sync succeeded;
a second synced document was deleted with zero remaining metadata, source files, or Qdrant points.
Focused pytest passed `30/30`; Ruff, format, ty, Compose config, image build, startup, and health
passed. Production object storage remains not active and no durability claim changed.

T14 and T18-T20 are externally accepted `PASS_WITH_NOTES`; T15-T17 are externally accepted
`PASS`. T21 Final Integration, Evaluation, and Portfolio Readiness is
`IN_PROGRESS / VERIFY_PENDING`
on `feat/t14-t21-enterprise-hardening`. Its deterministic evaluation, final local integration
gates, architecture/portfolio/evidence/interview documentation, and final PR body are prepared.
Hosted PR, publication, attestation, cloud, and production evidence remain outside this stage. It
does not create the PR, merge `main`, or publish a release. The active plan is
[`docs/exec-plans/active/T21.md`](../exec-plans/active/T21.md).

## T21 Final Integration Evidence

- The first backend attempt remains invalid/incomplete: it collected `1848` tests and stopped near
  5% because `asyncpg` timed out through `localhost`. A direct `127.0.0.1` connection succeeded;
  PostgreSQL was healthy. Its classification remains `TEST_ENVIRONMENT` and it is not final evidence.
- The explicitly authorized replacement used `127.0.0.1`, a fresh isolated database, writable OS
  temp/cache paths, Redis DB 15, a process-scoped Qdrant collection, memory Celery transports, and
  real providers disabled. Preflight passed 3/3 focused migration/tenant/API tests.
- The replacement full suite ran exactly once to completion: `1848` collected, `1810` passed,
  `1` failed, `0` errors, `37` skipped, `81.93%` coverage, `2231.21s` (`37:11`).
- The full regression completed with one historical nondeterministic timing failure and zero
  demonstrated T21 feature regressions. The sole failure was
  `tests/test_chat_api.py::test_chat_timeout_after_answer_closes_without_error`, classified as
  `NON_REPRODUCIBLE_PREVIOUS_FAILURE`. Focused control evidence was T21 `5/5` passing, accepted T20
  `4/5` with the same failure, and protected `origin/main` `4/5` with the same failure. No code in
  the failing execution path changed. This is its own historical chat-stream timing flake, not the
  OpenAI or Celery timing debt. **T21 feature regression: NO.**
- Remaining local gates passed: frozen frontend install, format, lint, typecheck, Vitest (`12` files,
  `51` tests), build, and browser E2E (`6/6`); clean-checkout Docker build/startup/health with
  synthetic configuration; Helm lint/template/schema/kubeconform (`42` valid resources) and
  ShellCheck; route inventory (`126` application HTTP policy routes, `2` WebSocket, `0` unclassified
  HTTP/WS); and the bounded final security/CI graph review. The complete inventory remains `136`
  entries (`130` HTTP including `4` framework routes, `2` WebSocket, and `4` mounts), which explains
  the earlier T19 total without any application route removal. The Playwright runner reported all
  six tests passing before a Windows Vite teardown hang required termination; no browser test failed.
- The provider-free offline evaluation remains reused at `12/12` scenarios, with no real provider.
  Hosted PR checks, trusted GHCR publication, image/SBOM attestation, and any external cloud proof
  remain pending. T21 is `IN_PROGRESS / VERIFY_PENDING`; no PR or merge exists.

## T21 Implementation Start

- Recovery began from a clean, synchronized branch at
  `d7acd74d0fddc9b4b539c8c8300c37617660b1d4`.
- The explicit T21 instruction accepts T20 as `PASS_WITH_NOTES`, satisfying the prerequisite.
- Existing evaluation infrastructure will be extended. Deterministic workflow checks remain
  distinct from optional live-model semantic quality evaluation.
- The OpenAI cold-start and Celery import timing debts, visible vulnerability baseline, hosted
  PR/GHCR/attestation proof, public VM/DNS/CA proof, object-store recovery, PITR, live AWS, long
  soak, and production-capacity evidence remain explicit limitations.
- The final PR and hosted proof remain later external-acceptance work; no PR or merge is authorized.

T19 is externally accepted `PASS_WITH_NOTES` by the explicit T20 implementation instruction.
T20 Performance, Failure, Backup, Restore, and Disaster Recovery is `AWAITING_ACCEPTANCE /
EXTERNAL_ACCEPTANCE_PENDING` on
`feat/t14-t21-enterprise-hardening`. T20 owns one bounded load harness, disposable dependency
failure and backpressure evidence, demo PostgreSQL backup/restore validation, persistence
classification, measured disposable recovery evidence, and operator runbooks. Production and
shared developer data are excluded. T21 final integration, hosted proof, PR, and closeout remain
`NOT_STARTED` and out of scope. The active plan is
[`docs/exec-plans/completed/T20.md`](../exec-plans/completed/T20.md).

## T20 Implementation Start

- Recovery started from clean, synchronized branch `feat/t14-t21-enterprise-hardening` at
  `bd524560606134f75eadba981904c7fd8dc00fe6`.
- The user explicitly accepted T19 as `PASS_WITH_NOTES`, satisfying the T20 prerequisite. T14 and
  T18 remain `PASS_WITH_NOTES`; T15-T17 remain `PASS`; T21 remains `NOT_STARTED`.
- Existing tooling is limited to pytest micro/performance regressions and the T19 Helm/k3s
  deployment. No version-controlled request-load harness, backup/restore automation, or T20
  failure matrix exists. T20 will reuse T17 telemetry and T19 topology rather than add competing
  systems.
- ADR-020 requires a real automated demo backup and restore test. Production-reference HA/PITR is
  documented architecture only in this local stage; no production RTO/RPO or HA claim will be
  made without provider evidence.
- Docker/k3d/Helm/k6 runtime availability must be established in a disposable environment before
  destructive evidence. No production or shared persistent developer resource is authorized.

## T20 Implementation Closeout

- One safe-by-default k6 harness, guarded failure/backup/restore scripts, a Helm demo PostgreSQL
  backup CronJob/bootstrap Job/PVC, performance/failure guidance, and dependency/DR runbooks are
  implemented. No route, application schema, provider traffic, production resource, PR, or T21
  work was added.
- Three identical disposable baselines completed 1,611 requests with zero failures at mean 14.46
  requests/s and 112.39/412.85/604.75 ms mean p50/p95/p99. A two-minute short soak completed 1,707
  requests with zero failures. These are local measurements, not capacity or SLA claims.
- Relay, worker, broker, API, scheduler, PostgreSQL, Redis, Qdrant, Mock-provider, and absent-
  telemetry-sink scenarios produced visible degradation and recovered. Peak Outbox/queue backlog
  was 10/5; all 19 protected effects completed with zero duplicate receipt keys or lost committed
  work.
- The source disposable namespace/PVCs were deleted after a checksummed backup. Fresh restore
  exposed and fixed portable-checksum and missing-ACL defects. A repeated fresh-database restore,
  normal migration/role provisioning, application login, RLS cross-tenant denial, business/audit
  sentinels, and post-restore async processing passed. PostgreSQL restore took 6 seconds and measured
  restore-to-service readiness was approximately 80 seconds in this disposable environment.
- Tested RPO is the selected completed logical backup; PITR is not implemented. Single-node k3s is
  not node HA. Object-storage durability is not claimed because the active T19 compatibility path
  is `emptyDir`; Qdrant remains rebuildable, Redis ephemeral, and RabbitMQ secondary to Outbox.
- The disposable cluster, namespaces, PVCs, network, volume, and k6 containers were removed. Only
  ignored local evidence was retained. T20 remains `IN_PROGRESS / VERIFY_PENDING`; external
  verification is required and T21 remains `NOT_STARTED`.

## T20 Verification Closeout

- Independent verification started from clean, synchronized `8c55131a16d81eed7521d8095ae96a43e66dece9` on
  `feat/t14-t21-enterprise-hardening`. Production, persistent developer databases, shared Redis,
  RabbitMQ, Qdrant, object storage, and real model providers were not touched. The only runtime
  target was disposable k3d cluster `t20v-20260917` (`k3d 5.9.0`, `k3s v1.35.5+k3s1`) with
  synthetic credentials and tenants.
- The safe-default k6 SMOKE passed once (39 requests, 100% checks). One bounded BASELINE spot-check
  passed 587/587 checks at 15.36 requests/s with p50/p95/p99 `94.18/355.74/840.39 ms`; API memory
  was 246->260 MiB, worker memory 207->205 MiB, and PostgreSQL activity was 9 connections. The
  higher single-run p99 was an endpoint-tail variance; throughput and p95 did not regress against
  the three-run implementation mean. No production capacity or SLA claim is made.
- Independent async integrity passed with 5/5 Outbox-to-RabbitMQ-to-Celery effects, unique receipts,
  zero loss, zero duplicate durable effects, and drained Outbox and business queues. Worker restart,
  relay pause/resume, and PostgreSQL outage/reconnect samples all passed; PostgreSQL outage produced
  a bounded login failure rather than false success, then recovered authenticated reads.
- A fresh 296047-byte PostgreSQL custom archive passed non-empty, SHA-256, metadata, and archive-list
  validation. Metadata identified timestamp, application/image revision, Alembic `e9f0a1b2c3d4`,
  disposable database identity, and backup type without credentials. A fresh target restore passed
  roles, RLS policies, required extension, application connectivity, deterministic business/audit/
  conversation/runtime sentinels, tenant isolation, and no-op migration at the accepted head.
- Both restore defects were independently regression-tested. A moved artifact passed the portable
  basename checksum path and full restore. A control restore using the former `--no-acl` behavior
  reproduced runtime `permission denied`, while the fixed ACL-preserving restore granted the fixed
  capability role and returned the expected tenant rows. No defect regressed.
- The end-to-end DR replay destroyed only the disposable source namespace/PVCs, created a fresh
  target environment, restored and migrated it, started the application, revalidated tenant and
  business invariants, and completed one new async effect exactly once. Measured local RTO from
  source-destroy initiation through post-restore async completion was approximately 665 seconds
  (11m05s), not a production target. Tested RPO is the latest completed logical backup; PITR is
  `NOT IMPLEMENTED`.
- Persistence classification remains explicit: PostgreSQL is authoritative; Qdrant is
  `DERIVED_REBUILDABLE` and its PostgreSQL/source-file reconciliation seam is covered by focused
  tests; Redis is `EPHEMERAL`; RabbitMQ is `DURABLE_SECONDARY` behind the PostgreSQL Outbox. No
  durable object-storage adapter is active, local uploads use transient `emptyDir`, and
  `OBJECT_STORAGE_RUNTIME_RECOVERY = NOT_EXERCISED`; PostgreSQL backup does not restore uploaded
  source bytes.
- Focused disposable RLS/database-role tests passed 14/14 and the selected T20/outbox/task-runtime/
  memory/route/migration/Celery tests passed 72/72. Ruff, format, ty, ShellCheck 0.11.0, Helm lint,
  route inventory (136 entries, 0 unclassified HTTP/WS), and the single Alembic head all passed.
  The known OpenAI cold-start and Celery fresh-process timing debt tests were not run. Initial
  disposable setup races and one operator copy naming omission were corrected in the test procedure,
  not in product code, and introduced no verification failure.
- The exact disposable cluster, namespaces, PVCs, network, port-forwards, temporary credentials,
  backup, k6 summaries, and raw verification directory were removed. T20 moves to
  `AWAITING_ACCEPTANCE / EXTERNAL_ACCEPTANCE_PENDING`; Codex does not mark it `PASS`. T21 remains
  `NOT_STARTED`, with no PR or merge created.

T18 CI/CD and Supply Chain is externally accepted `PASS_WITH_NOTES` by the explicit T19
implementation instruction. T19 Production Deployment Baseline is now `AWAITING_ACCEPTANCE /
EXTERNAL_ACCEPTANCE_PENDING`
on `feat/t14-t21-enterprise-hardening`. Its frozen scope is one Helm chart for the existing API,
worker, scheduler, and outbox-relay process boundaries; an immutable T18 image-consumption
contract; a low-cost k3s demo profile; secure configuration, migration, ingress, and observability
integration; and an AWS EKS reference architecture. T20 performance, failure, backup/restore, DR,
and capacity work and T21 final hosted proof remain out of scope.

## T19 Implementation Start

- Recovery started from clean branch `feat/t14-t21-enterprise-hardening` at `8802702`; no existing
  Helm, Kubernetes, Terraform, or competing application deployment system was found.
- ADR-015 and ADR-016 match the explicit T19 instruction: Docker Compose remains local, k3s plus
  Helm is the public-demo target, and AWS EKS with managed data/service boundaries is reference
  architecture only. The active plan is
  [`docs/exec-plans/completed/T19.md`](../exec-plans/completed/T19.md).
- T18 is accepted `PASS_WITH_NOTES` by explicit user instruction. Hosted registry publication and
  attestation proof remain deferred to T21; T19 configures the immutable GHCR consumption boundary
  without publishing an image.
- The implementation will not modify application business code or migrations. The accepted single
  Alembic head remains `e9f0a1b2c3d4`.

## T19 Implementation Closeout

- T19 implementation is complete and remains `IN_PROGRESS`; execution advances to
  `VERIFY_PENDING`. Codex does not mark T19 `PASS`.
- Added one canonical Helm chart with default, low-cost k3s demo, and qualified production-reference
  values; a values schema; explicit API, tenant worker, maintenance worker, singleton scheduler,
  singleton outbox relay, and revision-scoped migration Job; TLS ingress; secret references;
  non-root security; baseline resources/probes; and optional PVC-backed demo dependencies.
- Trusted main/version-tag CI now publishes the exact scanned T18 image to GHCR by immutable commit
  tag and digest and attests that subject. Pull requests remain read-only and never publish.
- A disposable k3d cluster running k3s `v1.35.5+k3s1` passed install, migration, pod readiness,
  HTTPS ingress health, service/endpoints, internal metrics/structured logging, benign upgrade,
  application rollback without schema downgrade, and a missing-Secret failure with successful
  atomic recovery. Strict kubeconform reported `38` valid resources and no errors.
- Helm lint/template passed for default/demo/production-reference values. ShellCheck and actionlint
  passed; rendered security/secret scans were clean; production missing-digest and default `latest`
  negative cases failed as required. Alembic remains `e9f0a1b2c3d4`, and direct route inventory
  reports `136` classified entries with `0` unclassified.
- Hosted GHCR runtime/attestation proof remains T21 evidence. A real public VM/DNS/CA deployment and
  live AWS resources were not created; AWS remains a documented reference. No T20 performance,
  resilience, backup/restore, DR, or capacity work was performed.

## T19 Verification Closeout

- T19 moves from `IN_PROGRESS / VERIFY_PENDING` to `AWAITING_ACCEPTANCE /
  EXTERNAL_ACCEPTANCE_PENDING`; Codex does not mark it `PASS`. T20 remains `NOT_STARTED`.
- Independent final verification passed on the synchronized `feat/t14-t21-enterprise-hardening`
  branch at `31536460a808cffa3847261d4db681a2086b9eb9` with a clean worktree. Helm lint/template,
  strict kubeconform (`38` valid, `0` invalid/errors/skipped), ShellCheck deployment scripts,
  production security render, immutable image negative cases, migration ownership, and route/Alembic
  guards passed.
- A fresh disposable k3d `5.9.0` cluster running k3s `v1.35.5+k3s1` in namespace `t19-verify`
  passed canonical install, API/worker/maintenance/scheduler/relay and demo dependency readiness,
  HTTPS ingress, upgrade with two API replicas, atomic migration and missing-Secret failures,
  application rollback without downgrade, bounded Pod termination, and singleton checks. No
  production namespace, database, credential, AWS resource, or image publication was touched.
- The migration Job was the only `alembic upgrade head` owner (parallelism/completions `1/1`); all
  application workloads used non-mutating `alembic current --check-heads`. PostgreSQL remained at
  `e9f0a1b2c3d4` after rollback. No migration history, application route, or business code changed.
- Browser/ingress verification preserved Secure HttpOnly cookies, CSRF, exact Origin behavior, no
  browser bearer/query token, valid cookie/origin WebSocket handshakes, query-token/invalid-Origin
  rejection, HTTPS OIDC callback configuration, and a small authenticated upload. Public metrics
  were not routed. SSE completion is explicitly unclaimed because no supported runtime Mock-provider
  fixture exists in the chart and no real provider was called; production ingress streaming/body
  annotations were verified.
- Helm OTLP configuration reached the existing T17 Collector/Tempo boundary. One API request
  produced a queryable four-span API trace, internal metrics and JSON API/worker logs were observed,
  and no disposable Secret sentinel appeared in logs or traces. Existing scheduled maintenance
  task tenant-context failures were observed in the reused T18 image and remain classified
  `PRE_EXISTING_BASELINE`; they are not a T19 chart defect and were not repaired in VERIFY.
- Hosted GHCR runtime/attestation proof remains deferred to T21. Public VM/DNS/CA proof remains
  deployment-environment deferred. AWS is reference-only. T20 performance, resilience,
  backup/restore, DR, and capacity work, plus OpenAI/Celery timing debt, was not performed.

T13 Model Gateway is externally accepted `PASS`. T14 AI Failure Policy is externally accepted
`PASS_WITH_NOTES` on the long-lived T14-T21 integration branch. T15 Frontend Transport, T16
Enterprise Console, and T17 Production Observability Hardening are externally accepted `PASS` by
the explicit T18 implementation instruction. T18 CI/CD and Supply Chain is externally accepted
`PASS_WITH_NOTES` on that same branch. M02's protected-main consolidation is complete; the accepted
baseline remains intact.

The T14 implementation adds a bounded, provider-neutral policy seam for retries, ordered fallback,
Redis-coordinated provider circuits, cancellation-safe streaming, and explicit safe degradation.
T13 adapters/gateway remain single-attempt/single-candidate components and T12 durable runtime
semantics remain unchanged. M02's protected-main consolidation used a verified linear PR branch
whose initial tree exactly matched the canonical local consolidation. The first PR run identified
two focused CI defects (optional tokenizer analysis and mismatched Qdrant smoke credentials); their
narrow fixes were merged and verified before protected-main consolidation. T14 is now
`PASS_WITH_NOTES`; T15 has implemented the canonical browser transport layer without changing
backend security or product APIs. T16 is extending the existing admin frontend with capability-
aware Overview, AI, Operations, Security, and Compliance surfaces over already accepted contracts.

The frozen product target is an **Enterprise Multi-tenant AI Customer Service Platform**: a runnable, testable, deployable portfolio and public demo that demonstrates enterprise controls truthfully. The primary Golden Path is tenant login → tenant context and authorization → PII filtering → intent and multi-agent routing → order adapter and hybrid RAG → model gateway → refund recommendation → human approval → refund transaction → transactional outbox → RabbitMQ/Celery → audit, memory, evaluation, notification, and observability.

# Historical T19 Task Snapshot

- **Task:** T19 - Production Deployment Baseline.
- **Status:** `AWAITING_ACCEPTANCE`.
- **Execution stage:** `EXTERNAL_ACCEPTANCE_PENDING`; the long-lived integration branch is
  `feat/t14-t21-enterprise-hardening`.
- **Scope:** Verify the canonical Helm/k3s deployment, immutable T18 image flow, secret boundary,
  release migration ownership, TLS ingress/browser-security compatibility, probes/lifecycle,
  observability configuration, and AWS reference architecture. T20 performance/DR and T21 final
  hosted gates remain out of scope.

## T18 Implementation Start

- The repository has no narrower tracked T18 plan; the explicit T18 implementation instruction and
  ADR-016 are the recovered frozen scope. The active plan is
  [`docs/exec-plans/completed/T18.md`](../exec-plans/completed/T18.md).
- Recovery confirmed a clean, synchronized `feat/t14-t21-enterprise-hardening` worktree at
  `5dd8bde`. The current CI retains Brand & docs, Backend quality, Backend tests, Frontend, and
  Docker smoke as separate attributable jobs; evaluation, monitoring, and performance workflows
  remain separate.
- The implementation must keep untrusted pull requests read-only and secret-free. Trusted main/tag
  provenance is a separate job boundary. The accepted Alembic head remains `e9f0a1b2c3d4`.

## T18 Implementation Closeout

- T18 implementation is complete and moves to `IN_PROGRESS / VERIFY_PENDING`; Codex does not mark
  the task `PASS`. The branch remains `feat/t14-t21-enterprise-hardening`; T19 and T20 remain
  `NOT_STARTED`.
- Preserved the five accepted CI families and added lock/migration checks, explicit Python/Node/npm
  versions, frozen installs, bounded reports, safe image metadata, current Debian runtime security
  updates, secret/dependency/image scans, CycloneDX SBOM generation, trusted-only provenance
  attestation configuration, PR Dependency Review, and trusted-context CodeQL.
- Local evidence passed for identity, workflow YAML/actionlint, uv lock/Ruff/format/ty, Alembic head,
  frontend gates, Docker build/non-root/metadata, disposable Compose migration/role/health smoke,
  Gitleaks, SBOM parsing, and image metadata. The rebuilt image has `0` critical Trivy findings;
  remaining dependency/image findings are visible warnings with machine-readable reports and no
  suppressions.
- Local audit baseline on 2026-09-16: backend pip-audit `83` records across `19` packages with no
  severity field in its JSON format; frontend npm audit `9` high, `4` moderate, `1` low, `0`
  critical; hardened image Trivy `0` critical, `81` high, `37` high with a known fix. No lockfile
  was updated to conceal or automatically remediate findings.
- Full backend regression, hosted protected-PR evidence, and trusted hosted attestation remain
  VERIFY/T21 acceptance work. OpenAI SDK and Celery fresh-process timing debt was not changed.

## T18 Verification Closeout

- T18 moves to `AWAITING_ACCEPTANCE / EXTERNAL_ACCEPTANCE_PENDING`; Codex does not mark it `PASS`.
  The branch remains `feat/t14-t21-enterprise-hardening`, T19 and T20 remain `NOT_STARTED`, and
  the final PR remains intentionally deferred until T21.
- Verification reconfirmed read-only workflow defaults, secret-free/unprivileged untrusted PR
  execution, no `pull_request_target`, immutable third-party action pinning, explicit runtime
  versions, frozen installs, PR cache isolation, and trusted-only attestation permissions.
- The five accepted CI families remain separate. Actionlint passed. Backend quality, frontend
  (`51` tests), Docker build/non-root/image-secret checks, Gitleaks, dependency-report parsing,
  Trivy policy, and CycloneDX 1.6 SBOM validation (`255` components) passed locally. Temporary
  altered manifests proved lock mismatch failure; a clean archive passed identity and uv lock
  checks. The full backend suite was intentionally not run.
- Vulnerability baseline remains visible: npm `0` critical / `9` high, pip-audit `83` records
  across `19` packages without severity fields, and Trivy `0` critical / `81` high with `37` known
  fixes. Findings are grouped with package/ID/fix/disposition detail in the active T18 plan; no
  suppressions or bulk upgrades were added. The pre-update image's critical Debian findings remain
  resolved by the bounded base-image security-update step.
- Protected-PR and trusted hosted attestation evidence remain `T21 FINAL GATE`. Main protection,
  reviewer policy, registry publication, image signing, deployment, routes, and migrations were
  not changed. The OpenAI/Celery timing debts remain deferred and untouched.

## T17 Implementation Start

- The repository planning ledgers contain no narrower T17-specific plan; the explicit T17 task
  instruction is therefore the recovered frozen scope for this stage.
- Initial inventory found application metrics and tracing primitives plus optional local Compose
  provisioning, but no canonical HTTP/worker/runtime metric contract, no bounded exporter-failure
  policy, stale dashboard/alert references, and a logging filter that did not cover sensitive
  structured fields. The active implementation plan is
  [`docs/exec-plans/completed/T17.md`](../exec-plans/completed/T17.md).
- The existing trusted `TaskContext`/`TaskEnvelope`, transactional outbox relay, RabbitMQ/Celery
  delivery, conversation state machine, and model gateway/failure-policy seam remain the owners
  of their semantics. Observability will consume those boundaries only.

## T17 Implementation Closeout

- T17 implementation is complete and moves to `IN_PROGRESS / VERIFY_PENDING`; Codex does not mark
  the task `PASS`.
- Reused the accepted OpenTelemetry, Prometheus/Mimir, Grafana, Loki/Promtail, Tempo, and
  Alertmanager stack. Added bounded metrics (including aggregate database query/pool/error
  signals), sanitized JSON logging, W3C/TaskEnvelope trace propagation,
  worker/outbox/conversation/model signals, three dashboards, eleven actionable rules, local no-op
  routing, and focused runbooks/tests.
- Preserved T02 trusted context, T03/T04 outbox and Celery delivery semantics, T12 terminal
  uniqueness, and T13/T14 logical-request/attempt and failure-policy semantics. No public business
  route, frontend change, migration, T18/T19/T20 work, or deferred baseline timing-debt repair was
  added.
- Local monitoring smoke passed for Prometheus, Mimir, Grafana, Loki, Tempo, Alertmanager, and the
  OTel Collector. A synthetic failure was correlated through Loki and Tempo using a safe correlation
  field and trace ID. The repository API was not started because an unrelated container occupied
  host port 8000; focused metric-registry evidence passed.
- Targeted instrumentation, logging, policy, monitoring, intent, and context tests passed along
  with Ruff format/check, ty, route classification, compile/import, config validation, and Alembic
  head checks. Existing DB/client fixture collection failures remain environment/test-infrastructure
  debt and are not T17 implementation failures.

## T17 Verification Attempt

- Attempted on 2026-09-16 against the canonical API, worker, scheduler, outbox relay, and disposable
  PostgreSQL/Redis/RabbitMQ/Qdrant runtime. The monitoring stack remained healthy and all temporary
  verification resources were removed afterward.
- Prometheus scraped the canonical API and observed the normalized `/api/v1/login` HTTP metric with
  bounded labels. The API container had the running Collector endpoint configured.
- A real API request carrying a valid W3C `traceparent` and correlation ID did not return `X-Trace-ID`.
  Tempo contained scheduler traces from the same Collector but no `star-warehouse-ai-api` trace.
  This is a real HTTP tracing acceptance failure, not a test-fixture failure.
- Primary classification: `TRACE_PROPAGATION_FAILURE`. No implementation change was made during
  VERIFY; T17 remains `IN_PROGRESS / VERIFY_PENDING` and is not ready for external acceptance.

## T17 API Trace Fix

- The focused fix started from synchronized head `a1a46cd7d7bc12d430def44dd3966b59dfbc198e`
  and reproduced the API trace failure for five of five sampled HTTP requests while scheduler
  traces continued to reach Tempo through the same Collector.
- Root cause classification: `API_TELEMETRY_INITIALIZATION_ORDER`. FastAPI instrumentation was
  installed from lifespan after Starlette had already built and cached its middleware stack, so
  the request path never entered OpenTelemetry middleware. The existing provider/exporter and
  Collector/Tempo path were not replaced.
- The existing bootstrap now installs the SDK provider and instruments the completed FastAPI app
  before its first ASGI call. The shared JSON handler also receives the existing correlation-ID
  filter so propagated application records contain correlation, trace, and span IDs together.
- Real-stack evidence passed: five of five requests returned the existing `X-Trace-ID` and were
  queryable in Tempo as `star-warehouse-ai-api`; the normalized HTTP metric, Loki JSON event, and
  Tempo trace correlated for one synthetic tenant-resolution failure. Scheduler traces remained
  queryable. Synthetic password and username values had zero Loki matches.
- Focused regressions passed `17`; changed-file Ruff, format, and ty checks passed. Route inventory
  remained `136` classified entries with `0` unclassified routes, and Alembic remained at the
  single head `e9f0a1b2c3d4`. No route, migration, Collector change, or T02/T03/T04 semantic change
  was added. Disposable containers, volumes, and evidence files were removed.
- T17 remains `IN_PROGRESS / VERIFY_PENDING`; the failed VERIFY gate must be resumed externally.
  T18 remains `NOT_STARTED`.

## T17 Verification Evidence Closeout

Completed: 2026-09-16

- T17 moves to `AWAITING_ACCEPTANCE / EXTERNAL_ACCEPTANCE_PENDING`; Codex does not mark the task
  `PASS`. T14 remains `PASS_WITH_NOTES`, T15/T16 remain `PASS`, and T18 remains `NOT_STARTED`.
- Evidence used only the disposable Compose project `star-warehouse-ai-t17evidence`: one existing
  admin/user/tenant fixture, one order/refund approval, a disposable PostgreSQL database, Redis
  database, Qdrant service, and RabbitMQ vhost. Fixture cleanup left tenant, user, outbox, and
  receipt counts at zero; the project containers, network, and volumes were then removed. The
  long-lived monitoring stack and other developer databases were not mutated.
- The real workflow passed end to end: API approval -> two transactional outbox events -> relay ->
  RabbitMQ test vhost -> two Celery tasks. Both refunds/outbox events completed, with two completed
  task receipts and no ACK, retry, or idempotency semantic change. API, outbox, and worker spans
  shared trace `b418288a455fd6f29ac25035c52f4222` using the accepted parent/child relationship.
- One fixed-path HTTP smoke remained green. A deterministic tenant-resolution rejection provided
  normalized failure metric, sanitized Loki JSON, and Tempo trace correlation. Mock T13/T14
  evidence preserved one logical request, three provider attempts, one retry, one fallback, and
  one terminal outcome; circuit CLOSED/OPEN/HALF_OPEN signals and one-terminal T12 runtime guards
  also passed.
- Stopping only optional Tempo did not affect the real business workflow: the request completed,
  the database transaction and async receipts committed, Collector retry behavior remained bounded
  by its queue/max-elapsed settings, and the trace became queryable after Tempo was restored.
- Runtime review checked 27 T17 metric families and effective Loki labels. No request, correlation,
  trace, span, tenant, user, conversation, run, URL, exception-message, prompt, or free-text label
  was found; provider/model identities remain bounded configured values. Four synthetic sentinel
  secrets were absent from application logs, Loki, and trace attributes.
- All three provisioned Grafana dashboards loaded and their representative Mimir queries evaluated
  successfully. Eleven T17 rules were loaded by the Grafana rule engine with severity, summary, and
  runbook metadata; Alertmanager loaded the local-no-op route without a real external secret. The
  canonical Mimir query API had no T17 series because its existing scrape target is a separate
  host-port service; the isolated API registry and metric/source tests provided the metric evidence.
- Compact semantic regression passed `29/29` selected T02/T03/T04/T12/T13/T14/T17 checks. Ruff,
  format, ty, Compose, Prometheus/rules, Alertmanager, OTel, route inventory, and Alembic checks
  passed. Route inventory remains `136` classified and `0` unclassified; the single head remains
  `e9f0a1b2c3d4`. No application code, frontend, migration, public route, or T18 work changed.
- OpenAI SDK cold-start and Celery fresh-process import timing remain deferred baseline debt and
  were not executed or repaired. Full backend and 288-test T17 matrices remain intentionally out
  of scope.

## T16 Implementation Closeout

- T16 implementation and final verification are complete; the task is now
  `AWAITING_ACCEPTANCE / EXTERNAL_ACCEPTANCE_PENDING`.
- The shared admin shell now owns capability-aware navigation and session/direct-route guards for
  Overview, Operations, AI, Security, Compliance, and the stable existing workspaces. New console
  reads and mutations use the T15 transport boundary and existing backend contracts only.
- Sensitive export content, provider credentials, passwords, session secrets, TOTP material, raw
  prompt/RAG content, and unredacted audit payloads are not rendered. General audit list/detail,
  async-job/outbox controls, provider/circuit administration, and tenant switching remain explicit
  backend gaps or out of scope.
- Frontend verification passed: format check, lint, TypeScript/build, Vitest `51 passed`, and
  Chromium E2E `6 passed`. Focused T15 transport guards passed `31 passed`.
- Focused backend evidence closeout passed authorization (`8` tests), compliance (`5` tests), and
  implemented operations/runtime/AI read endpoints (`4` tests) against the disposable
  `test_t16_evidence_20260915` database on the repository's Compose PostgreSQL, with existing
  capability roles and Redis DB 15 available. The default host ports were occupied by unrelated
  containers, so loopback-only evidence ports were used without changing repository configuration.
- The route inventory reported zero unclassified HTTP/WS routes, Alembic remained at the single
  head `e9f0a1b2c3d4`, and no implementation defect, migration, or new T16 debt was added.

## T16 Verification Closeout

- Focused Chromium acceptance passed `5` tests: authorized overview/operations navigation,
  capability-denied direct route, explicit backend 403, compliance approval with confirmation/
  CSRF/refresh, and browser-session login/logout.
- T16-targeted frontend tests passed `23` tests across `5` files. Format, lint, explicit TypeScript
  check, and production build all passed. No full frontend suite was rerun.
- Compact backend smoke passed `8` tests: authorization allow/deny (`3`), compliance approval and
  requester access-loss behavior (`2`), and implemented conversation/dashboard/AI reads (`3`).
- Structural review confirmed one shared shell, server-derived capability visibility, explicit 401/
  403 handling, scoped cache clearing/invalidation, canonical T15 transport, no browser Bearer or
  token URL/storage path, no secret rendering, and no unsupported provider/job/outbox/audit controls.
- Route inventory remains `0` unclassified HTTP/WS routes and Alembic remains at the single head
  `e9f0a1b2c3d4`. No migration or historical migration modification was added.
- T16 is not marked `PASS` by Codex; external acceptance is now required before T17.

# Historical T15 Task

- **Task:** T15 – Frontend Transport.
- **Status:** `AWAITING_ACCEPTANCE`.
- **Execution stage:** `EXTERNAL_ACCEPTANCE_PENDING`; the long-lived integration branch is
  `feat/t14-t21-enterprise-hardening`.
- **Scope:** Canonical browser HTTP, SSE, WebSocket, auth-state, CSRF, error, timeout, cancellation,
  retry, and security-guard behavior. No T16 console work, backend security weakening, migration,
  or protected-main baseline-debt repair. Targeted frontend, browser, T10, T12, and T14
  compatibility verification has passed; T15 is awaiting external acceptance.

# Independent Maintenance Task

- **Task:** M01 — Repository Consolidation & Legacy Cleanup.
- **Status:** `PASS` (externally accepted).
- **Isolation:** M01 did not change T06 acceptance/evidence status or start T07.
- **Plan:** [`docs/exec-plans/completed/M01.md`](../exec-plans/completed/M01.md).
- **Evidence ledger:** [`REPOSITORY_CLEANUP.md`](REPOSITORY_CLEANUP.md).

# Historical Accepted-Task Snapshot

`T15` - Frontend Transport, externally accepted `PASS` by explicit user acceptance instruction
on 2026-09-15.

# Historical T14 Last Accepted Task

`T14` – AI Failure Policy, externally accepted `PASS_WITH_NOTES` on 2026-09-15.

# Historical T16 Next-Task Snapshot

`T16` - Enterprise Console is `AWAITING_ACCEPTANCE / EXTERNAL_ACCEPTANCE_PENDING` on the
long-lived integration branch; external acceptance is required before T17.

# Historical T15 Next Task

`T16 – Enterprise Console` remains `NOT_STARTED` and cannot begin until T15 is externally accepted.

T14 started only after T13 was fully verified and externally accepted. T14 remains
`PASS_WITH_NOTES` after explicit external acceptance. T15 is now
`AWAITING_ACCEPTANCE / EXTERNAL_ACCEPTANCE_PENDING` and follows the recorded IMPLEMENT → VERIFY
→ external acceptance sequence.

# T14 Verification Closeout

Completed: 2026-09-15

Status: `PASS_WITH_NOTES` (externally accepted)

Execution Stage: `EXTERNAL_ACCEPTANCE_COMPLETE`

- The final clean-checkout backend regression completed without fail-fast: `1819 collected`,
  `1780 passed`, `2 failed`, `0 errors`, `37 skipped`, and `81.62%` coverage. Both failures
  reproduce on protected `main` and the T14 branch; no feature-only T14 failure was observed.
- T14-specific verification is complete; feature-only regressions = `0`.
- `DEFERRED_BASELINE_TEST_DEBT`: OpenAI SDK cold-start deadline sensitivity
  and Celery fresh-process import deadline sensitivity. Both debts reproduce on protected
  `main`, are not attributed to T14, remain unresolved, and do not block T15.
- All nine T14/T12/T13 critical guards pass. RedisVL, generic Redis, and circuit cleanup pass;
  Qdrant has no test collections remaining; RabbitMQ remains under the documented memory-broker
  policy; and no unexpected provider network or credential use occurred.
- No implementation, test, migration, or T14 policy changes were made during closeout. The
  feature branch remained clean and unmerged; T15 was not started at that historical closeout.

# T14-T21 Integration Workflow

T14 through T21 use one long-lived integration branch:
`feat/t14-t21-enterprise-hardening`.

Each stage follows `IMPLEMENT → VERIFY → external acceptance → next stage`.
There is no PR or branch per T-stage, no mandatory human reviewer, and no direct work on
`main`. Each stage keeps logically separated commits. Use normal pushes only; do not force push
to `main`. One final PR is planned after T21, with automated CI gates retained.

## Test strategy and failure triage

- Normal `IMPLEMENT` uses targeted tests.
- Normal `VERIFY` uses targeted/regression tests appropriate to the changed subsystem.
- Full backend verification is not mandatory after every T-stage. Run it for a cross-cutting or
  high-risk stage, when a blocker needs proof, at T21/final integration, and in final CI/PR.
- A feature-only reproducible failure is a current-stage blocker.
- The same failure on protected `main` receives baseline-debt classification first.
- A non-reproducible transient failure is recorded without inventing a fix.
- An environment failure is fixed in the environment, not in business code.
- Historical debt is not infinitely cleaned during unrelated feature work.

## Deferred baseline test debt

`DEFERRED_BASELINE_TEST_DEBT` remains recorded for OpenAI SDK cold-start deadline sensitivity and
Celery fresh-process import deadline sensitivity. Repair these only if final integration CI is
blocked, they become materially worse, or explicit test-hardening work is scheduled. They remain
unresolved and do not block T15.

# Current Architecture Baseline

The authoritative frozen choices are recorded in [`DECISIONS.md`](DECISIONS.md). In summary:

- Modular monolith; API, Celery worker, scheduler/Beat, and outbox relay are independent deployment boundaries.
- Progressive seam-first refactoring; no Big Bang rewrite and no unsolicited business expansion.
- Shared database/schema with `tenant_id`, PostgreSQL RLS, ORM filtering, and tenant isolation across task, Redis, Qdrant, and object-storage boundaries.
- Local account plus OIDC identity binding (`issuer + subject`), RBAC, scopes, membership, route policy, revocation, and audit; authentication, authorization, and tenant context remain distinct.
- HttpOnly/Secure/SameSite browser cookies with CSRF and Origin validation for sensitive operations; no localStorage JWT or WebSocket URL token as the target design.
- PostgreSQL transaction → transactional outbox → relay → RabbitMQ → Celery → idempotency guard → handler. Redis is for cache, sessions/revocation, rate limits, locks, short-lived state, and circuit state.
- Explicit Task Context/Envelope carries tenant, user, correlation, trace, idempotency, and sanitized payload data across process boundaries.
- Unified Model Gateway: OpenAI primary, DashScope real fallback, Mock provider for tests/evaluation/load/fault injection.
- Compliance controls follow classify → redact → process → store → retain → export → erase → audit; no certification claims.
- Evaluation combines deterministic checks, LLM-as-a-Judge, and human sample review; observability uses correlated request/trace/task/outbox/provider identifiers.
- Local demo uses Docker Compose; public demo targets low-cost k3s/Helm; AWS EKS is a production reference. Demo topology is not production topology.
- Disaster recovery: Demo requires real automated backups and a Restore Test; the Production Reference requires HA and PITR, explicit RPO/RTO, a Restore Runbook, and recovery verification evidence. Demo and Production may use different topologies and cost tiers.
- Existing frontend is extended with an Enterprise Console; it is not comprehensively rewritten. External business systems use high-fidelity sandbox adapters.

# Known P0/P1 Issues

T02 closed the first two confirmed request-to-task risks, and T03 closed the post-commit intent-loss window for migrated critical paths. Remaining risks stay owned by their mapped later tasks:

1. **P0-1 Async tenant context loss — RESOLVED_T02:** Request-sourced tasks carry a validated tenant envelope, bind it before I/O, and clean it after execution; missing tenant fails closed.
2. **P0-2 Raw PII persistence — RESOLVED_T02:** Chat observability, token usage, evaluation, and memory task payloads use redacted/minimal data; the HTTP-to-worker-to-database regression contains no original phone/email.
3. **P0-3 Memory dual-write consistency — RESOLVED_T05:** Structured summary/tombstone state and minimal vector intent share one PostgreSQL transaction; the reliable worker reloads authoritative content and projects a stable, versioned Qdrant point. Verification passed.
4. **P0-4 Lost async side effects — RESOLVED_T03:** Migrated critical refund/order and knowledge-indexing paths persist a pending outbox event in the caller-owned business transaction; relay publication is retryable and at-least-once.

The complete concise mapping is in [`ARCHITECTURE_GUARDRAILS.md`](../architecture/ARCHITECTURE_GUARDRAILS.md). T01 does not claim to remediate any item.

# Environment Status

- Repository: `D:\star-warehouse-ai`.
- Branch at T-INIT start: `main`.
- Base HEAD at T-INIT start: `bf0d5b9`.
- Execution-time environment: Windows PowerShell workspace; Python 3.12.10, uv 0.6.5, Node v22.23.2, and npm 10.9.8.
- Docker Client 29.4.3, Docker Engine 29.4.3, and Docker Compose 5.1.3 are available. The project Compose stack was built and run on temporary non-conflicting host ports; unrelated user containers were not changed, and project volumes were not deleted.
- Existing CI is GitHub Actions with brand/docs, backend quality/tests, frontend, Docker smoke, evaluation, monitoring, and performance workflows.

# Verification Status

- Backend dependency synchronization, Ruff, format check, ty, full pytest/coverage, application import, Alembic runtime, and Compose syntax were run with recorded results in [`baselines/T00_BASELINE.md`](baselines/T00_BASELINE.md).
- Frontend dependencies, the authorized repository formatter, format check, lint, unit tests, and production build passed. The 95 previously failing files were formatting-only changes.
- T01 backend Ruff and ty passed; the changed migration-test file passes Ruff format check.
- The architecture-specific migration guardrail passed with 3 tests using `--noconftest`; the default focused invocation was intercepted by the repository-wide database fixture because the local `.env` resolves PostgreSQL as Compose host `db`.
- The guardrail source contains G1–G12 and maps confirmed debt through T02–T17. Project identity/local documentation links and `git diff --check` pass.
- The T00 formal backend CI entry point remains 1533 tests passed with 79.43% coverage; T01 did not rerun the full suite because it changed documentation and one lightweight static regression test only.
- Alembic has one head, `b7c6d5e4f3a2`. A new empty PostgreSQL database upgraded to that head, and `message_feedbacks` contains the expected enrichment columns and indexes. Docker runtime smoke remains passed from T00-FIX.
- T02 focused regressions: 58 passed, covering envelope validation, tenant/correlation/trace binding, cleanup/isolation, missing-tenant worker rejection, stable idempotency identity, PII-safe persistence, and migrated request task paths.
- T02 full backend gate: 1542 passed with 80.12% coverage (`--cov-fail-under=75`). Ruff, Ruff format check, and ty pass for `app` and `tests`; the no-direct-Celery-publication static guard passes.
- T03 focused regressions: 68 passed, covering atomic rollback/commit, recovery, retry, publication success, lease/concurrent claim safety, duplicate semantics, tenant propagation, PII rejection, publisher adaptation, and critical-path static guards.
- T03 full backend gate: 1558 passed with 80.18% coverage (`--cov-fail-under=75`). Ruff, Ruff format check, and ty pass for `app` and `tests`.
- Alembic has one head, `c8d7e6f5a4b3`. A fresh PostgreSQL database upgraded to head; `outbox_events`, its uniqueness/check constraints, and relay indexes were verified.
- T04 targeted regressions: 86 passed, covering receipt crash recovery, duplicate-safe refund effects, bounded retry, retry exhaustion/permanent failure, DLQ publication failure requeue, explicit system contexts, T03 outbox regressions, and three real RabbitMQ integration tests.
- T04 real-broker evidence: RabbitMQ was healthy; an unacknowledged delivery was redelivered after connection loss; terminal JSON evidence persisted in `critical.dlq`; and Outbox -> RabbitMQ -> Celery worker executed one database effect across duplicate delivery.
- T04 full backend gate: 1574 passed with 80.38% coverage (`--cov-fail-under=75`). Ruff, Ruff format check (373 files), ty, Compose syntax, project identity/local links, and `git diff --check` pass.
- Alembic has one head, `d9e8f7a6b5c4`. A disposable empty PostgreSQL 16 database upgraded through the complete chain; `task_execution_receipts`, its tenant/handler/idempotency uniqueness constraint, and recovery index were verified.
- T05-IMPLEMENT targeted regressions: 43 passed, covering cross-session persistence, rollback, Qdrant failure/recovery, shared receipt deduplication, stale-event protection, delete intent and delete retry, tenant isolation, reconciliation, stable point replacement, and structured-memory read degradation.
- T05-IMPLEMENT scoped quality gates: Ruff PASS, Ruff format check PASS (14 files), ty PASS with `--error-on-warning`; migration import/compile sanity PASS and Alembic reports the single head `e3f4a5b6c7d8`.
- T05-VERIFY targeted regressions: 48 passed, including migration-chain, cross-session persistence, rollback, Qdrant failure/recovery, duplicate/stale protection, delete consistency, and tenant isolation.
- T05-VERIFY full backend gate: 1583 passed, 3 skipped, 80.45% coverage (`--cov-fail-under=75`). Repository-wide Ruff, format check, and ty all pass.
- T05-VERIFY fresh PostgreSQL database upgraded successfully to the single head `e3f4a5b6c7d8`. RabbitMQ redelivery and Outbox → RabbitMQ → Celery worker duplicate-safe smoke tests pass; authenticated local Qdrant-backed suite passes with localhost proxy bypass.

# T06 Implementation Evidence

- Targeted tenant gates: 60 passed, covering canonical/missing/unknown/inactive resolution, ORM read/write/delete and relationship isolation, Redis namespace/cleanup isolation, Qdrant query/delete isolation, TaskContext tenant revalidation, local knowledge storage prefixing, migration-chain checks, and T05 memory behavior.
- Corrected ORM/Qdrant subset after type-only test edits: 3 passed.
- Scoped Ruff, Ruff format check, and ty with `--error-on-warning`: PASS.
- Alembic reports the single head `f4a5b6c7d8e9`.
- T06 VERIFY-RETRY runtime infrastructure was restored with the existing Compose service definitions on temporary non-conflicting host ports; PostgreSQL, Redis, and Qdrant reported healthy, and host/in-network reachability probes passed.
- T06 critical tenant rerun: 84 passed, 14 warnings. Tenant resolution/fail-closed, ORM read/write/relationship, Redis, Qdrant, TaskContext, and T05 memory/vector isolation evidence passed.
- T06 fresh PostgreSQL database migration: PASS; forward upgrade succeeded, Alembic reports the single head `f4a5b6c7d8e9`, and the tenant/backfill/default-column inspection passed (`tenant_rows=1`, `tenant_id_defaults=0`, `tenant_id_tables=39`).
- T06 full backend gate reached coverage but did not pass: 1573 passed, 3 skipped, 11 failed, 13 errors; coverage 78.49% with the 75% threshold reached. Remaining failures are test-fixture/transaction/dependency/event-loop and documentation-link issues; no T06 critical isolation assertion failed.
- Repository-wide Ruff, format check, and ty remain PASS from the prior verification and were not repeated; no runtime code was changed in VERIFY-RETRY.
- T07 inventory is classified: tenant-owned/global tables have no ambiguous SQLModel tables; RLS inventory readiness is YES. No RLS work was performed.
- T06-FIX-TX makes the registration route/application use case the single transaction owner. The transaction commits before the successful response returns and rolls back automatically on failures; `AuthService.register_user()` remains a nested query/add/flush collaborator with no hidden commit.
- Registration transaction targeted verification: 27 passed, covering durable visibility from an independent session, rollback after a staged insert, duplicate/conflict atomicity, directly related auth/registration regressions, and tenant fail-closed behavior.
- T06-FIX-TX scoped Ruff, Ruff format check, and ty with `--error-on-warning`: PASS.
- T06-FIX-FIXTURES stale chat/performance/task nodes: PASS, 16 tests.
- T06-FIX-FIXTURES revoked-token, fail-closed tenant, durable-registration, and WebSocket security smoke: PASS, 11 tests.
- T06-FIX-FIXTURES affected-file Ruff, format check, and ty with `--error-on-warning`: PASS.
- T06-FIX-FIXTURES changed only test fixtures/tests and test guidance; production behavior and Tenant Architecture are unchanged.
- T06-FINAL-VERIFY full backend gate: PASS, 1604 passed, 3 skipped, 0 failed, 0 errors, 80.58% coverage.
- T06-FINAL-VERIFY Alembic heads: PASS, single head `f4a5b6c7d8e9`; no migration history changed.
- T06-FINAL-VERIFY preflight: PostgreSQL, Redis, Qdrant, and RabbitMQ PASS. The first Qdrant-proxy-routed invocation was discarded as environment evidence; the corrected loopback host configuration passed.

# T07 Implementation Evidence

- Added canonical transaction-local PostgreSQL setting `app.current_tenant_id`, bound centrally for
  async and sync SQLAlchemy sessions from the existing `TenantContext`; missing runtime context
  binds an empty transaction-local value and fails closed.
- Added migration `a5b6c7d8e9f0` after accepted head `f4a5b6c7d8e9`: all 39 accepted tenant-owned
  tables use `ENABLE ROW LEVEL SECURITY`, `FORCE ROW LEVEL SECURITY`, and an `ALL` policy with
  structural `USING` and `WITH CHECK`; tenant ID remains `VARCHAR(64)` and no historical migration,
  uniqueness constraint, business data, or speculative index was changed.
- Added fixed `NOLOGIN`/`NOINHERIT`/`NOBYPASSRLS` runtime and maintenance capability roles plus
  separate configured least-privilege login provisioning; Alembic keeps the administrative URL,
  normal API/tenant workers use runtime capability, and outbox/scheduled maintenance uses an
  independently deployed maintenance capability.
- Real PostgreSQL RLS integration: PASS, 9 tests on a disposable database migrated to head. Raw
  cross-tenant reads, direct-ID read/update/delete, cross-tenant insert, missing context, same-pool
  A-to-B-to-none reuse, worker propagation, runtime-role reality, maintenance scoping, and the full
  catalog inventory all passed.
- Existing T06 application tenant guard subset: PASS, 16 tests. Migration-chain guard: PASS, 7
  tests. Compose/Celery startup and capability separation: PASS, 8 tests. Dedicated-credential
  fail-closed configuration guard: PASS, 4 tests.
- Scoped Ruff, Ruff format check, and ty with `--error-on-warning`: PASS. Python compile/import,
  Compose config, and Alembic single-head checks passed; head is `a5b6c7d8e9f0`.
- Escape-hatch audit found no normal runtime `row_security=off`, superuser/table-owner execution,
  `BYPASSRLS`, privileged raw URL, admin-credential fallback, or RBAC-selected maintenance
  capability; admin reuse is restricted to databases explicitly named with the `test_` prefix.

# T07 Final Verification Evidence

- Preflight passed: repository Compose config, PostgreSQL, Redis, RabbitMQ, and Qdrant health checks.
- Fresh disposable PostgreSQL database upgraded through `a5b6c7d8e9f0`; actual catalog inspection
  found 39 expected tables, 39 forced-RLS tables, and 39 structural policies.
- Disposable database upgraded from accepted `f4a5b6c7d8e9` with seeded Tenant A/B data; head,
  preserved rows, forced RLS, runtime raw isolation, blocked B mutation, and pooled A -> B -> none
  context sequence all passed.
- One real RabbitMQ/Celery worker task using the runtime login and `TaskEnvelope` returned only the
  bound Tenant A row. Runtime/maintenance role separation and no-assume checks passed.
- Full command `uv run pytest --cov=app --cov-fail-under=75`: `1621 collected; 30 passed; 0 failed;
  1591 errors; 0 skipped; 40.64% coverage; 2350.20s`. The root error is the shared cleanup fixture
  executing `TRUNCATE` through the runtime capability, rejected with
  `asyncpg.exceptions.InsufficientPrivilegeError: permission denied for table task_execution_receipts`.
  Classified `REGRESSION` (test fixture/least-privilege mismatch); no implementation change was made
  during VERIFY.

# T07-FIX-TEST-CLEANUP Evidence

- Replaced the runtime-role `_truncate_leaky_tables` path with an explicit session-scoped
  `test_maintenance_engine` backed by the existing migration/admin URL. The connection is marked
  test-harness-only and never enters application, repository, API, or worker paths; no tenant
  context is bound for global cleanup.
- Preserved the intentional cleanup list and `TRUNCATE ... RESTART IDENTITY CASCADE` transaction
  behavior. Added regression guards proving maintenance cleanup succeeds and a runtime session is
  denied `TRUNCATE` on `task_execution_receipts`.
- Targeted PostgreSQL verification on disposable `test_t07_cleanup`: cleanup/runtime privilege
  guards `2 passed`; task receipt, chat/API, auth, memory, and shadow-task setup samples `5 passed`;
  raw cross-tenant RLS smoke `1 passed`.
- Scoped Ruff, format check, and ty for changed test files passed. Alembic remains at one head,
  `a5b6c7d8e9f0`; no production RLS, migration, or role grant changed.

# T07-FINAL-VERIFY Evidence

- Preflight passed for PostgreSQL, Redis, RabbitMQ, Qdrant, and Compose configuration. The full
  run used isolated PostgreSQL `test_t07_final_regression`, runtime login `t07_final_runtime`,
  Redis DB 15, and a run-scoped Qdrant collection; real RabbitMQ tests remained skipped because
  `T04_RABBITMQ_URL` was not configured, per the existing test convention.
- The two privilege safety guards passed immediately before the full run: explicit maintenance
  cleanup succeeded and the effective `star_warehouse_runtime` session was denied `TRUNCATE`.
- `uv run pytest --cov=app --cov-fail-under=75` collected `1623` items and finished with `1618
  passed, 2 failed, 3 skipped`, `80.73%` coverage, and `998.74s` pytest elapsed (`1022.80s`
  shell elapsed). The prior cleanup setup cascade did not recur.
- Failure 1: `tests/graph/test_memory_integration.py::test_memory_node_routes_to_supervisor` —
  `RLS_REGRESSION`; the T07 database session refresh hook causes three concurrent structured-memory
  queries to raise `InvalidRequestError: This session is provisioning a new connection; concurrent
  operations are not permitted`, leaving `structured_facts` absent.
- Failure 2: `tests/performance/test_performance.py::test_cache_reduces_latency` —
  `PRE_EXISTING_OTHER`; the timing assertion observed `2.3749ms` cache-hit versus `2.1214ms`
  cache-miss in the full run, while the isolated node rerun passed.
- The single-head check remains `a5b6c7d8e9f0`; no production RLS, migration, or privilege change
  was made during FINAL_VERIFY.

# T07-FIX-RLS-CONCURRENCY Evidence

- Exact race: combination A+B. Four structured-memory reads shared one `AsyncSession` under
  `asyncio.gather`, and their first ORM executions concurrently entered the tenant refresh hook
  while the session was provisioning its connection/transaction. The binding SQL was already
  guarded after a stable transaction, so excessive successful rebinding was not the cause.
- Concurrent reads now own independent sessions and transactions. `after_begin` performs the
  initial transaction-local tenant binding; refresh no longer eagerly provisions a connection and
  remains limited to an already-active transaction whose trusted tenant changed after resolution.
- Original graph integration plus session ownership: `2 passed`. Disposable PostgreSQL same-tenant,
  cross-tenant, A -> B -> no-context pool, raw RLS, and worker smoke set: `5 passed`.
- Scoped Ruff, format, and ty passed. The performance timing test and full backend suite were not
  run; no production security control or T05 memory semantics were weakened.

# T07-FINAL-VERIFY-RECHECK Evidence

- Preflight passed: PostgreSQL, Redis, RabbitMQ, and Qdrant were reachable/healthy. Isolated test
  configuration used `test_star_warehouse_ai`, Redis DB 15, a process-scoped Qdrant collection,
  runtime capability for application sessions, the explicit migration/admin URL for cleanup, and
  the in-memory broker transport because no dedicated `T04_RABBITMQ_URL` was configured.
- Safety smoke passed: runtime `TRUNCATE` denied, maintenance cleanup succeeded, the original graph
  memory regression passed, and the concurrent same-tenant memory regression passed.
- Full command `uv run pytest --cov=app --cov-fail-under=75` passed: `1626 collected`, `1623 passed`,
  `0 failed`, `0 errors`, `3 skipped`, `80.67%` coverage, and `970.62s` pytest elapsed (`16:10`).
  The performance timing test passed in this run.
- `uv run alembic heads` passed with the single expected head `a5b6c7d8e9f0`.
- Ruff, format, and ty remain inherited PASS evidence because no implementation files were modified
  during final verification; no production architecture or RLS behavior changed.

# T08 Implementation Evidence

- Local password login and existing application JWT issuance are preserved behind a normalized
  authentication principal that carries no tenant selection or authorization decision.
- Generic OIDC discovery, cached JWKS with unknown-key refresh, asymmetric token verification,
  issuer/audience/time/subject checks, state, nonce, and PKCE S256 are implemented.
- Durable `issuer + subject` binding is database-enforced at the single Alembic head
  `b6c7d8e9f0a1`; verified-email first linking is disabled by default and remains explicitly gated,
  tenant-scoped, active-user-only, conflict-safe, and non-provisioning when enabled.
- The final targeted suite passed: `40 passed` in `25.65s`, including local authentication,
  revocation, hostile token/linking cases, concurrency, tenant boundary, migration guards, and the
  real Keycloak discovery/JWKS/RS256 identity path.
- Fresh disposable PostgreSQL upgrade/catalog inspection, scoped Ruff, format, ty, Compose identity
  profile, realm JSON, and targeted diff hygiene all passed; browser E2E is not claimed.
- Full backend/frontend regression was intentionally not run during IMPLEMENT; final verification
  ran the full backend regression while frontend remains out of scope, and T09/T10 remain
  `NOT_STARTED`.

# T08 Final Verification Evidence

- `external_identities` is classified `TENANT_OWNED`: the actual fresh schema has `tenant_id`, a
  local-user foreign key, tenant and user indexes, global `issuer + subject` uniqueness, forced
  RLS, and the `USING`/`WITH CHECK` tenant policy. The runtime capability saw the binding in tenant
  A and zero rows in tenant B; no implicit tenant access was possible.
- A fresh disposable PostgreSQL database reached `b6c7d8e9f0a1`; catalog inspection confirmed the
  table, issuer, subject, user relationship, required indexes, unique constraint, and forced RLS.
- A seeded local user survived the `a5b6c7d8e9f0` to `b6c7d8e9f0a1` upgrade and authenticated with
  the existing application JWT path.
- The live Keycloak profile passed runtime, discovery, JWKS, password-grant RS256 validation, and
  issuer/subject resolution. Browser E2E was not claimed.
- The compact identity/security regression passed `13` tests, including local compatibility,
  durable changed-email resolution, cross-issuer protection, unverified-email rejection,
  disabled-user rejection, no implicit tenant access, token negatives, and concurrent linking.
- The full backend regression passed: `1646 collected; 1642 passed; 0 failed; 0 errors; 4 skipped;
  80.72% coverage; 1025.64s` pytest elapsed. Alembic has one head: `b6c7d8e9f0a1`.
- Secret/logging safety passed with no private key, JWT-like token, raw authentication token, or
  complete authorization code/client secret in authentication logs. Ruff, format, and ty remain
  inherited `PASS` evidence because VERIFY changed no implementation files.
- An initial full-run attempt exposed only environment/documentation defects: plain Redis lacked
  `FT._LIST`, and a stale link referenced archived T07. Redis Stack was selected and the link was
  corrected; the exact full command then passed.

# T09 Implementation Evidence

- One current-state authorization model now resolves the authenticated local user against the
  trusted tenant-owned `User` membership on every protected HTTP request and WebSocket connection;
  JWT and OIDC role/scope claims are not effective authority.
- The centralized dotted-scope policy inventory classifies 120 HTTP method/routes and 2 WebSocket
  routes, with zero unclassified production entries. Startup rejects unknown routes and protected
  HTTP entries without the canonical authorization dependency.
- Immediate role and membership revocation, cross-tenant denial, read/mutation separation,
  self-elevation prevention, last-admin safety, local/OIDC convergence, and transactionally atomic
  mutation audit evidence passed targeted API/PostgreSQL checks.
- The targeted authorization/security/WebSocket/migration-chain selection passed `53` tests. A
  fresh-migration RLS selection passed `3` tests, including application `SUPER_ADMIN` isolation.
- The additive `c7d8e9f0a1b2` upgrade from accepted T08 head preserved a seeded administrator and
  created the authorization audit relation with forced RLS; Alembic remains single-head.
- Repository-wide Ruff check, Ruff format check, and ty with `--error-on-warning` pass. The complete
  backend pytest/coverage suite was deliberately not run during IMPLEMENT.

# T09 Final Verification Evidence

- Preflight passed: `docker compose config`, isolated PostgreSQL, Redis, Qdrant, and the project
  RabbitMQ container were reachable. Existing unrelated containers were not modified; temporary
  T09 PostgreSQL/Redis/Qdrant containers used non-conflicting ports.
- `authorization_audit_events` is confirmed `TENANT_OWNED`: live schema inspection found the
  required `tenant_id`, foreign keys, primary/tenant/actor/target/action/correlation indexes,
  `ENABLE + FORCE ROW LEVEL SECURITY`, and one forced-RLS policy with both `USING` and `WITH CHECK`.
  A least-privilege runtime session saw Tenant A only, saw zero rows without context, and was denied
  a rollback-only Tenant B insert. Runtime and maintenance roles remained non-superuser and
  non-`BYPASSRLS`.
- Fresh PostgreSQL migration passed through `c7d8e9f0a1b2`; upgrade from `b6c7d8e9f0a1` passed with
  seeded tenant/user/SUPER_ADMIN state preserved. Alembic reports one head, `c7d8e9f0a1b2`.
- Final application inventory passed with 120 classified HTTP routes, 2 classified WebSocket routes,
  4 classified mounts, zero unclassified production routes, and no sensitive business/admin route
  classified `PUBLIC`. The structural guard rejected an injected unclassified route.
- The focused T09 authorization module passed `21` tests, including runtime authorization,
  same-JWT role and membership revocation, OIDC/local convergence, privilege escalation, atomic
  audit behavior, and both WebSocket policy paths. Infrastructure-independent route/policy checks
  passed `4` tests.
- Required full backend regression did not pass: `1666 collected; 1630 passed; 24 failed; 30 errors;
  4 skipped; 79.27% coverage; 1125.63s (18:45)`. The failed set was outside the T09 targeted
  authorization gates: 22 Qdrant failures/errors were reproduced as loopback proxy routing and the
  affected 23-test selection passed with `NO_PROXY=127.0.0.1,localhost`; 8 Redis workflow errors
  reproduced the existing RedisVL restriction that RediSearch indexes cannot use test DB 15; and
  2 legacy admin tests still assert the superseded `Admin privileges required` detail while the
  current deny-by-default policy returns `Access is not permitted`.
- Failure classification: `PRE_EXISTING_OTHER`. No tracked production implementation file changed
  during this verification; T09 static PASS evidence is inherited. T10 remains explicitly not started.

# T09 Regression Repair Evidence

- The focused Qdrant regression group passed `22` previously affected tests. `tests/_db_config.py`
  now preserves existing proxy bypass entries and adds `localhost`, `127.0.0.1`, and `::1` before
  application imports, keeping host-process Qdrant requests on the local endpoint; container
  Compose service addressing is unchanged.
- RedisVL 0.16.0 rejects RediSearch index creation on DB 15 (`Cannot create index on db != 0`).
  The generic Redis fixture remains on DB 15, while `redis_checkpointer` uses DB 0 only with
  per-fixture checkpoint/index prefixes and scoped index teardown; DB 15 and ordinary keyspace
  state were not modified.
- The two legacy admin API assertions now verify the existing stable `403` detail
  `Access is not permitted`; no handler or authorization policy changed. The admin API file passed
  `15` tests, the focused authorization smoke passed `4` tests, the isolated SUPER_ADMIN/RLS smoke
  passed `1` test, and scoped Ruff, format, and ty passed.
- Full backend regression and coverage remain pending and are intentionally assigned to the final
  T09 verification stage.

# Current Blockers

- M02 has no current repository-history ambiguity. The protected-main PR, required checks, linear
  merge, remote verification, and post-merge cleanup are complete and externally accepted.
- The extensive pre-existing dirty worktree is
  preserved and overlaps configuration, graph, agents, services, tests, and documentation.
- T13 remains externally accepted `PASS`; T14 is externally accepted `PASS_WITH_NOTES`.
  T15 is awaiting external acceptance; the two deferred baseline debts do not block it.

# T13 Implementation Evidence

- One canonical `ModelGateway` now resolves configuration-driven use-case routes to ordered,
  capability-declared candidates. OpenAI is primary, DashScope is the real alternate, and the
  deterministic Mock uses the same provider port.
- All retained production remote-chat call paths use the gateway seam; real provider SDK imports
  are confined to provider adapters. Existing embedding/reranking ports and local FastEmbed/BM25
  remain outside the chat-model scope.
- Real calls are async, explicitly timed, and configured with SDK retries disabled. The gateway
  invokes one selected candidate only; T14 still owns retry, automatic fallback, circuit breaking,
  degraded answers, and failure budgets.
- Targeted gateway/adapter/compatibility coverage passes (`44 passed`), the isolated direct-SDK
  structural guard passes (`2 passed`), and a deterministic persisted T12 runtime flow plus
  cancellation race passes through the Mock provider without public internet.
- Ruff, Ruff format check, ty, project identity, lock consistency, `git diff --check`, route
  classification, and the single Alembic head `e9f0a1b2c3d4` pass. T13 adds no route, table, or
  migration.

# T14 Implementation Evidence

- The feature branch `feat/t14-ai-failure-policy` starts from synchronized `main` at
  `1b76ab2e2e3fa2afc81155fd529b38251c36ef50`; `main` was not modified or merged.
- `ModelFailurePolicy` is the provider-neutral owner of finite retries, bounded exponential
  backoff/jitter, ordered fallback, Redis-coordinated provider circuits, cancellation handling,
  and explicitly marked safe-static degradation. `ModelGateway` and every provider adapter remain
  single-candidate/single-attempt boundaries; no provider SDK import was added to the policy.
- Factory-created clients use trusted `MODEL_FAILURE_*` settings and the shared Redis system
  namespace. The default degradation mode is fail-only, security/non-operational errors do not
  retry or trip circuits, and streaming never switches providers after visible output.
- Focused T14 tests pass (`23 passed`), the provider-neutral Model Gateway regression passes
  (`66 passed`), Ruff/format/ty pass on touched code, project identity passes, `uv lock --check`
  passes, and Alembic remains a single head at `e9f0a1b2c3d4`.
  T14-specific verification is complete; feature-only regressions = `0`; the full backend
  regression recorded two protected-main baseline debts. No migration or T15 work was added.

# Historical Implementation Notes

The entries below preserve historical execution context; current outstanding work is governed by
the canonical state at the top of this document and the latest execution entry.

- T-INIT/T-INIT-FIX documentation, accepted T00–T02 work, migration compatibility repair, test-fixture updates, and the tracked .dockerignore/.gitignore correction are uncommitted. These pre-existing changes were preserved through T03 implementation.
- T00 fixed reproducibility defects in SlowAPI configuration decoding, Docker build context, Alembic ordering/duplicate DDL, tenant-namespaced test fixtures, portable path assertions, and external-task isolation. The full backend suite now passes.
- T01 added the architecture guardrail source, ADR-021, root/documentation routing, evidence-qualified README wording, and the exact-one-Alembic-head regression; it is externally accepted.
- T02 added the typed task-runtime context/envelope/dispatch/binding seam, migrated all request-side Celery publication through it, protected telemetry and memory payloads from supported raw PII, and documented that delivery remains direct/non-durable until T03/T04.
- T03 added the outbox model/migration, transaction-owned enqueue API, concurrent-safe relay, Celery publisher Port/adapter, critical refund/order and knowledge-indexing migrations, and at-least-once failure/duplicate semantics.
- T04 moved the Celery broker to RabbitMQ, added critical/default/maintenance queues, protected refund receipts and retry/DLQ policy, explicit Beat system contexts, and real broker integration coverage. Global exactly-once is not claimed.
- T05-IMPLEMENT replaced the structured-summary direct dual write with a PostgreSQL summary/tombstone plus minimal Outbox event, reused the T04 receipt lease for stable external projections, added version ordering, delete recovery, reconciliation, and explicit vector-read degradation.
- T06-IMPLEMENT added the Tenant registry/status resolver, removed implicit production fallback, strengthened ORM mutation/relationship guards, unified Redis/Qdrant/local-storage tenant namespaces, and published the T07-ready table inventory; it is externally accepted `PASS`.
- T08 added generic OIDC discovery/JWKS and authorization-code validation, durable external identity
  binding, explicit fail-closed first linking, a Keycloak demo profile, and focused security tests.
- T09 added current PostgreSQL-backed membership/role resolution, canonical capability policy,
  explicit HTTP/WebSocket inventory enforcement, guarded role/membership administration, and
  transactionally atomic authorization audit evidence.
- The accepted T08 plan is archived at [`docs/exec-plans/completed/T08.md`](../exec-plans/completed/T08.md).
- The accepted T09 plan is archived at [`docs/exec-plans/completed/T09.md`](../exec-plans/completed/T09.md).
- The accepted T10 plan is archived at [`docs/exec-plans/completed/T10.md`](../exec-plans/completed/T10.md).
- The accepted T11 plan is archived at [`docs/exec-plans/completed/T11.md`](../exec-plans/completed/T11.md).
- The accepted T12 plan is archived at [`docs/exec-plans/completed/T12.md`](../exec-plans/completed/T12.md).
- The accepted T13 plan is archived at [`docs/exec-plans/completed/T13.md`](../exec-plans/completed/T13.md).
- The accepted T14 plan is archived at [`docs/exec-plans/completed/T14.md`](../exec-plans/completed/T14.md).

# Handoff Notes

1. T14 is externally accepted `PASS_WITH_NOTES`; its plan is archived under `completed/`.
2. The long-lived integration branch is `feat/t14-t21-enterprise-hardening`; T15 is next and
   remains `NOT_STARTED`.
3. T14-specific verification is complete with zero feature-only regressions. The OpenAI SDK
   cold-start and Celery fresh-process import sensitivities remain unresolved baseline debt and
   do not block T15.
4. Preserve the provider-neutral T14 seam and the accepted T00-T13/M01 baseline. T14 through
   T21 follow the recorded IMPLEMENT → VERIFY → external acceptance workflow.

# T09 Final Verification Regression Result

Completed: 2026-09-13

Status: `BLOCKED`

Execution Stage: `VERIFY_PENDING`

- Preflight passed for PostgreSQL, Redis, RabbitMQ, Qdrant, Compose syntax, canonical test
  isolation, and loopback proxy exclusion. The final smoke passed one Qdrant regression test, one
  RedisVL checkpointer test, one admin 403 contract test, same-JWT role revocation, and the route
  inventory guard (`5 passed`).
- The required command `uv run pytest --cov=app --cov-fail-under=75` completed in `943.73s`
  (`0:15:43`): `1666 collected; 1593 passed; 16 failed; 20 errors; 37 skipped; 79.29% coverage`.
  The repaired Qdrant proxy, RedisVL DB isolation, and legacy admin assertion groups did not
  recur.
- Failure groups are classified as `ENVIRONMENT` for 13 memory/workflow/performance failures and
  20 context errors caused by denied downloads of `cl100k_base.tiktoken`, and for one sparse
  embedder failure caused by a denied Hugging Face model download; `FIXTURE_REGRESSION` for the
  collection-time OIDC `nbf` case (the six-case selection passes in isolation); and
  `PRE_EXISTING_OTHER` for the unrelated zero-vector safety fallback assertion.
- Post-suite Qdrant collections and RedisVL DB 0 indexes/checkpoint keys were clean. Generic Redis
  DB 15 contained only `test:`-prefixed keys, with no non-test keys or RedisVL indexes. Alembic
  still reports the single head `c7d8e9f0a1b2`.
- No authorization, RLS, production Qdrant networking, or production Redis architecture changed.
  Static evidence remains inherited `PASS` for Ruff, format, and ty. T10 remains `NOT_STARTED`.

# T09 Final Hermetic Full Regression Result

Completed: 2026-09-13

Status: `BLOCKED`

Execution Stage: `VERIFY_PENDING`

- PostgreSQL, Redis, RabbitMQ, Qdrant, Compose syntax, canonical isolated endpoints, and loopback
  proxy exclusion passed. The six-test final smoke passed the no-download provider guard, OIDC
  future-`nbf`, both safety fallback cases, same-JWT role revocation, and the route inventory guard.
- The exact `uv run pytest --cov=app --cov-fail-under=75` command passed: `1673 collected; 1636
  passed; 0 failed; 0 errors; 37 skipped; 80.58% coverage; 969.37s (0:16:09)`. The 37 skips
  remain the repository's existing intentional optional/integration skips; no new skip was added.
- Hermetic tokenizer/embedding paths produced no external download errors and no test-only model
  cache warm-up was used. Qdrant finished with zero collections, and the generic Redis client used
  the dedicated DB 15 test store.
- RedisVL isolation is not proven: DB 0 has no remaining search index, but `144` raw LangGraph
  checkpoint/registry keys remain after the run. The installed saver fixture drops its indexes but
  does not remove its unindexed `checkpoint_latest`/`write_keys_zset` keys; this is classified as
  `REDISVL_TEST_INFRA` and was not fixed in final verification. No `FLUSHALL` was issued.
- Alembic remains a single head at `c7d8e9f0a1b2`; authorization, RLS, OIDC validation, production
  Redis, production Qdrant networking, and safety policy were not changed in this verification.

State transition:

- T08 remains `PASS`.
- T09 remains `BLOCKED / VERIFY_PENDING` because the full-suite RedisVL cleanup gate is not green.
- T10 remains `NOT_STARTED`; no later task was started.

# T09 Hermeticity, OIDC Time, and Safety Repair Evidence

Completed: 2026-09-13

Status: `BLOCKED`

Execution Stage: `VERIFY_PENDING`

- Application-owned tokenizer and sparse-provider seams keep normal tests independent of external
  tokenizer/model downloads while preserving real production providers. The affected matrix passed
  `37` tests with one existing optional real-LLM skip and two explicit no-download guards.
- Hostile OIDC claims now use fresh timezone-aware UTC timestamps immediately before signing. The
  future-`nbf` case passed alone, and all six neighboring security cases passed after unrelated tests
  in the same process; production OIDC validation was unchanged.
- Layer 3 safety treats unusable embedding evidence as degraded and executes deterministic keyword
  fallback. Dangerous and harmless zero-vector cases, provider failure, and valid embeddings passed
  in a `41`-test combined safety/OIDC group.
- Same-JWT role revocation, route inventory denial, and SUPER_ADMIN RLS independence passed `3`
  focused tests. Scoped Ruff, format, and ty passed.
- T09 remains `BLOCKED / VERIFY_PENDING` pending final full backend verification. T10 remains
  `NOT_STARTED`.

# T09 RedisVL Cleanup Repair Result

Completed: 2026-09-13

Status: `BLOCKED`

Execution Stage: `VERIFY_PENDING`

- The leak was reproduced on clean Redis DB 0: deleting the two RedisVL indexes left the global
  `checkpoint_latest:*` pointer and `write_keys_zset:*` registry keys. The installed saver writes
  those auxiliary keys outside its configured document prefixes, while their pointer values and
  sorted-set members retain the run-specific checkpoint/write prefixes.
- The test-only `cleanup_redisvl_resources` helper now drops indexes, removes exact run-prefixed
  leftovers, deletes only latest pointers whose values belong to the current run, and removes only
  current-run members from shared registry sorted sets using SCAN. Mixed-run and sentinel tests
  prove another run and unrelated DB0/DB15 data survive cleanup.
- RedisVL/checkpointer tests passed `11` with `1` existing optional skip; cleanup ownership and
  repeated-lifecycle tests passed `3`; the requested T09 smoke passed `2`. Clean-room DB0 and DB15
  post-checks both reported zero residual keys, and no FLUSHALL/FLUSHDB or shared-store mutation was
  used.
- Scoped Ruff, format, and ty passed. No authorization, RLS, production Redis, Celery broker, or
  other production architecture changed; the full backend coverage run remains pending.

State transition:

- T08 remains `PASS`.
- T09 remains `BLOCKED / VERIFY_PENDING` pending the final full backend regression.
- T10 remains `NOT_STARTED`; no later task was started.

# T09 Final Acceptance Verification Result

Completed: 2026-09-13

Status: `AWAITING_ACCEPTANCE`

Execution Stage: `EXTERNAL_ACCEPTANCE_PENDING`

- Preflight passed for PostgreSQL, Redis, RabbitMQ, Qdrant, Compose syntax, canonical isolated
  endpoints, and loopback proxy exclusion. The five-test final smoke passed RedisVL cleanup and
  sentinel protection, same-JWT revocation, route inventory, and zero-vector safety fallback.
- The exact `uv run pytest --cov=app --cov-fail-under=75` command passed: `1676 collected; 1639
  passed; 0 failed; 0 errors; 37 skipped; 80.59% coverage; 923.01s (0:15:23)`. The skip count did
  not increase and no regression was converted into a skip.
- Post-suite RedisVL DB0 contained zero indexes and zero current-run registry resources; the DB0
  sentinel remained present. Generic Redis DB15 preserved its sentinel, Qdrant had zero collections,
  and no shared-store flush or destructive cleanup was used.
- Normal tests required no external tokenizer/model download and no test-only cache warm-up. Alembic
  remains a single head at `c7d8e9f0a1b2`; accepted authorization, RLS, OIDC, safety, and production
  Redis/Qdrant boundaries remain unchanged.

State transition:

- T08 remains `PASS`.
- T09 is now `AWAITING_ACCEPTANCE / EXTERNAL_ACCEPTANCE_PENDING`; all final verification gates passed.
- T10 remains `NOT_STARTED`; no later task was started.

# T10 Implementation Start

- External acceptance received on 2026-09-13: `T09 = PASS`.
- Recovery confirmed branch `main`, HEAD `bf0d5b9`, and an extensive pre-existing dirty worktree
  containing accepted T00–T09 enterprise-hardening work; unrelated changes must remain untouched.
- T09's accepted plan is archived at [`docs/exec-plans/completed/T09.md`](../exec-plans/completed/T09.md).
- T10 is `IN_PROGRESS / IMPLEMENT`; T11 remains `NOT_STARTED`.
- The accepted T10 plan is [`docs/exec-plans/completed/T10.md`](../exec-plans/completed/T10.md).

# T10 Implementation Result

Completed: 2026-09-14

Status: `IN_PROGRESS`

Execution Stage: `VERIFY_PENDING`

- Browser local login and OIDC completion now set one host-only HttpOnly application-JWT cookie;
  production Secure and explicit SameSite defaults are settings-enforced, and cookie lifetime is
  bounded by the JWT expiry. Existing non-browser Bearer clients retain the same principal path.
- Signed session-bound CSRF plus exact Origin/Referer validation protects unsafe cookie requests;
  deterministic dual-credential handling prevents header-based CSRF bypass. Logout revokes before
  clearing the cookie, and T09 current-state authorization remains immediate for cookie sessions.
- Browser WebSockets authenticate from the cookie with trusted Origin and T09 route scope. Query
  tokens are rejected, expired/revoked credentials and cross-tenant authority fail closed, and the
  frontend no longer builds token-bearing WebSocket URLs.
- Frontend JWT persistence and reconstructed Authorization headers are removed; `/me` restores
  identity, credentials are included, CSRF is memory-only, server logout is authoritative, and only
  the known legacy `auth-storage` credential key is removed.
- Targeted backend tests passed `28`; frontend unit tests passed `9`; targeted Chromium passed `1`;
  scoped Ruff, format, ty, ESLint, Prettier, and TypeScript checks passed. Static credential scans
  were clean. Alembic remains one head at `c7d8e9f0a1b2`, with no T10 migration.
- Full backend regression, full relevant frontend regression/build, live browser/backend integration,
  and post-suite route/security guards remain assigned to Luna VERIFY. T11 was not started.

# T10 Final Verification Result

Completed: 2026-09-14

Status: `AWAITING_ACCEPTANCE`

Execution Stage: `EXTERNAL_ACCEPTANCE_PENDING`

- Recovery confirmed T09 `PASS`, T10 `IN_PROGRESS / VERIFY_PENDING`, T11 `NOT_STARTED`, branch
  `main`, and HEAD `bf0d5b9`; no implementation files were changed during VERIFY.
- PostgreSQL, Redis, RabbitMQ, Qdrant, Docker Compose syntax, and Playwright runtime preflight
  passed. The compact T10 HTTP/WebSocket security smoke passed `22` tests.
- The complete backend command passed `1690` collected, `1686` passed, `0` failed, `0` errors,
  `4` skipped, `80.91%` coverage, in `1227.08s (0:20:27)`.
- Canonical frontend checks passed: Vitest `7` files / `17` tests, ESLint, Prettier, TypeScript,
  and production build. Focused Chromium browser E2E passed `1` test, including HttpOnly cookie
  inspection, empty auth storage, CSRF mutation, and logout unauthenticated reload.
- Focused RedisVL cleanup, generic Redis isolation, and Qdrant run-scoped cleanup checks passed;
  existing development resources were retained and no shared-store flush or destructive cleanup
  was used. Alembic remains the single head `c7d8e9f0a1b2` with no T10 migration.
- Cookie configuration, static credential scan, CSRF/session binding, Origin/CORS, Bearer
  compatibility, ambiguity handling, logout revocation, same-cookie authorization revocation,
  OIDC callback confidentiality, WebSocket cookie/origin/scope/revocation/query-token rejection,
  route inventory, sensitive logging, and frontend transport gates all passed.

State transition:

- T09 remains `PASS`.
- T10 is `AWAITING_ACCEPTANCE / EXTERNAL_ACCEPTANCE_PENDING`; all final verification gates passed.
- T11 remains `NOT_STARTED`; no later task was started.

# T11 Implementation Result

Completed: 2026-09-14

Status: `IN_PROGRESS`

Execution Stage: `VERIFY_PENDING`

- T10's explicit external acceptance `PASS` was recovered and its plan remains archived under
  `docs/exec-plans/completed/T10.md`; T12 remains `NOT_STARTED`.
- The canonical registry classifies 51 datasets (45 SQLModel production tables plus six external
  or system stores), including 44 tenant-owned database tables and one global `tenants` table;
  unclassified production tables: zero.
- Bounded retention, dry-run, deterministic cutoff, tenant predicates, local-object cleanup,
  idempotent retries, kill-switch, maintenance scheduling, and low-cardinality metrics are
  implemented; audit evidence is retained indefinitely by explicit policy.
- Compliance and authorization audit events are append-only for runtime/application SUPER_ADMIN
  identities through PostgreSQL grants and triggers; sensitive feedback export uses exact,
  tenant-bound, requester-bound, expiring, single-use approval with current authorization checks.
- Targeted `tests/compliance` passed `20`; the existing export regression selection passed `2`, pure
  migration-chain assertions passed `10`, and the real PostgreSQL immutable-audit boundary passed
  `1`. Scoped Ruff format/lint and ty passed; Alembic has one head `d8e9f0a1b2c3`.
- Luna VERIFY still owns full backend regression, fresh/upgrade migration execution, runtime
  retention integration, post-suite audit/approval/RLS checks, and final route inventory; the full
  backend suite was not run during T11 IMPLEMENT.

State transition:

- T10 remains externally accepted `PASS`.
- T11 remains `IN_PROGRESS / VERIFY_PENDING`.
- T12 remains `NOT_STARTED`; no later task was started.

# T12 Implementation Result

Completed: 2026-09-14

Status: `IN_PROGRESS`

Execution Stage: `VERIFY_PENDING`

- PostgreSQL is the durable source for tenant-owned conversations, turns, runs, ordered lifecycle
  events, async tool identities/results, and the one logical terminal assistant `MessageCard`.
  RedisVL/checkpoints remain run-isolated executor acceleration; token chunks remain transient.
- `ConversationRuntime` is the canonical seam and delegates only through `ConversationExecutor`;
  LangGraph types, event parsing, and checkpoint namespaces live in `LangGraphConversationExecutor`,
  with a structural test preventing API imports of graph internals.
- Same-conversation mutating submissions serialize through PostgreSQL advisory transaction locks
  and return explicit conflict while an active run exists; actual async tests prove different
  conversations remain concurrent. Tenant/conversation/idempotency uniqueness returns the same
  logical turn/run for browser retries and rejects key reuse with a different message.
- Central lifecycle states are `PENDING`, `RUNNING`, `WAITING_TOOL`, `WAITING_HUMAN`, `COMPLETED`,
  `FAILED`, and `CANCELLED`. Logical cancellation is idempotent and terminal; run/turn/tool/tenant
  identity plus revisions prevent late or wrong-run results from mutating the current run.
- Durable per-run event sequences support replay after `last_seen_sequence`; authenticated runtime
  routes expose status/final result, replay, and logical cancellation without starting execution.
  Bounded orphan reconciliation marks stale non-terminal work `FAILED / ORPHANED_RUN` without retry.
- Additive migration `e9f0a1b2c3d4` creates five tenant-owned runtime tables with immediate forced
  RLS and `USING`/`WITH CHECK`, extends `MessageCard` with nullable durable identity, and registers
  all new datasets in T11 classification/retention policy. A fresh full-chain migration and direct
  database tenant-isolation smoke passed; Alembic has one head.
- Targeted evidence: `36` runtime tests, `13` chat/runtime transport tests, `12` existing
  graph/intent/multi-intent/memory/review compatibility tests, `2` fresh-migration RLS tests, `11`
  migration-chain tests, and `3` classification/route guards passed. Scoped Ruff, format, ty, and
  diff hygiene pass.
- Existing graph tools remain synchronous, so T12 adds no background tool dispatch transaction;
  the async result boundary propagates trusted `TaskContext`, while established T03/T04 async
  business paths remain unchanged. AI graph interrupt/resume is `N/A` because no `interrupt()`
  runtime exists; existing review-ticket resolution compatibility passed.
- The complete backend suite was not run by explicit IMPLEMENT instruction. T12 remains
  `IN_PROGRESS / VERIFY_PENDING`; T13 remains `NOT_STARTED`.

# T11 Final Verification Result

Completed: 2026-09-14

Status: `NEEDS_EVIDENCE`

Execution Stage: `VERIFY_BLOCKED`

- Infrastructure preflight passed for PostgreSQL, Redis, RabbitMQ, Qdrant, and canonical M01
  isolation. The fresh migration/RLS integration group passed `13`, and the isolated upgrade from
  `c7d8e9f0a1b2` preserved seeded data and reached `d8e9f0a1b2c3` without running retention.
- Runtime retention passed `6` focused tests, approval/export API and service flows passed `8`,
  classification/audit-redaction passed `3`, metrics/routes passed `3`, RedisVL/generic Redis
  cleanup passed `3`, and Qdrant tenant cleanup passed `4`.
- The final inventory is `51` classified datasets (`48` tenant-owned, including tenant-scoped
  derived/object stores, and `3` global/system) with zero unclassified production datasets. The
  runtime route inventory is `127` HTTP, `2` WebSocket, `4` mounts, and zero unclassified routes;
  sensitive compliance routes are not PUBLIC. Runbooks and unsupported-certification search pass.
- The required full backend command collected `1712` tests: `1705 passed`, `3 failed`, `0 errors`,
  `4 skipped`, `80.98%` coverage, and `1543.50s (0:25:43)`. Failures are classified as
  `ROUTE_INVENTORY` (legacy assertion expects 122 HTTP entries while the final inventory has 127)
  and `PRE_EXISTING_OTHER` (one timing-sensitive cache benchmark, which passed on focused rerun;
  the stale T10 active-plan documentation link is now synchronized to `completed/T10.md`).
- Static gates remain inherited `PASS` for Ruff, format, and ty; Alembic reports the single head
  `d8e9f0a1b2c3`, and no implementation files were changed during VERIFY. T11 cannot move to
  external acceptance until the focused route-test fix is applied and the full gate is rerun.

State transition:

- T10 remains externally accepted `PASS`.
- T11 moves from `IN_PROGRESS / VERIFY_PENDING` to `NEEDS_EVIDENCE / VERIFY_BLOCKED`.
- T12 remains `NOT_STARTED`; no later task was started.

# T11 Final Regression Fix Result

Completed: 2026-09-14

Status: `BLOCKED`

Execution Stage: `VERIFY_PENDING`

- The stale route-count assertion was replaced with a structural guard. The final runtime inventory
  remains `127` classified HTTP routes, `2` classified WebSocket routes, and `0` unclassified
  production routes; the five T11 additions and the approval-gated feedback export are all
  tenant-scoped and non-PUBLIC. The focused route/security selection passed `4` tests.
- The cache benchmark failure was test noise: the prior mock returned no profile, so a cache hit was
  not guaranteed and one wall-clock sample was scheduler-sensitive. The test now seeds a
  serializable profile, warms and clears the exact key, measures five miss/hit pairs, and compares
  medians; five sequential executions passed, with miss/hit medians of `2.26/1.12`, `2.33/1.23`,
  `1.87/1.01`, `2.40/1.51`, and `1.93/1.10` ms. Production cache behavior and architecture were
  not changed.
- The archived T10 reference in `PROJECT_STATE.md` now resolves to the canonical
  `docs/exec-plans/completed/T10.md` path; the focused project-identity/link check passed `2` tests.
- The T11 security smoke passed `3` focused approval/retention tests and `1` real PostgreSQL
  immutable-audit boundary test. Targeted Ruff, format, and ty checks pass; Alembic remains one
  head at `d8e9f0a1b2c3`.
- No production compliance, authorization, RLS, browser-session, or cache architecture changed;
  only focused regression tests and execution-state documentation were updated. The full backend
  regression and post-suite verification remain pending by task instruction.

State transition:

- T10 remains externally accepted `PASS`.
- T11 remains `BLOCKED / VERIFY_PENDING`; the focused final-regression blockers are repaired, but
  the full backend gate is still required before external acceptance.
- T12 remains `NOT_STARTED`; no later task was started.

# T11 Final Verification Result

Completed: 2026-09-14

Status: `AWAITING_ACCEPTANCE`

Execution Stage: `EXTERNAL_ACCEPTANCE_PENDING`

- Context recovery confirmed T10 `PASS`, T11 `BLOCKED / VERIFY_PENDING` before this final gate,
  T12 `NOT_STARTED`, branch `main`, and HEAD `bf0d5b9`. PostgreSQL, authenticated Redis, RabbitMQ
  management, and Qdrant readiness preflight passed; the canonical Redis/RedisVL/Qdrant isolation
  configuration remained in effect.
- Final smoke passed `7` focused tests plus `1` real PostgreSQL immutable-audit boundary test. The
  runtime inventory is `127` classified HTTP routes, `2` classified WebSocket routes, and `0`
  unclassified production routes; sensitive compliance routes remain non-PUBLIC.
- The required full backend command passed: `1712` collected, `1708 passed`, `0 failed`, `0 errors`,
  `4 skipped`, `80.98%` coverage, and `1488.90s (0:24:48)`. No new skips or xfails were introduced;
  the skipped integration cases are the pre-existing Keycloak/RabbitMQ environment-gated tests.
- Post-suite isolation checks passed `8` tests covering RedisVL scoped cleanup, generic tenant/system
  Redis preservation, and Qdrant run-scoped cleanup. T11 object lifecycle cleanup remains covered by
  the existing passing compliance tests; no residual test artifacts were reported.
- Alembic remains a single head at `d8e9f0a1b2c3`; historical migration files were not changed by
  this VERIFY thread. Existing Ruff, format, and ty evidence remains PASS, and no implementation
  architecture changed.

State transition:

- T10 remains externally accepted `PASS`.
- T11 moves from `BLOCKED / VERIFY_PENDING` to `AWAITING_ACCEPTANCE / EXTERNAL_ACCEPTANCE_PENDING`;
  external acceptance is required and T11 is not marked `PASS`.
- T12 remains `NOT_STARTED`; no later task was started.

# T12 Final Verification Result

Completed: 2026-09-14

Status: `NEEDS_EVIDENCE`

Execution Stage: `VERIFY_BLOCKED`

- Infrastructure preflight passed for isolated PostgreSQL, Redis Stack, RabbitMQ, and Qdrant; a
  dedicated `test_t12_verify` RabbitMQ vhost with scoped permissions was created for verification
  isolation.
- Route diff passed: T11's accepted `127` HTTP routes equal the current registered set after
  removing four framework routes and the three additive T12 runtime routes. No T11/T10 route was
  removed, both WebSockets remain, sensitive routes remain non-PUBLIC, and unclassified production
  routes are `0`.
- Fresh migration passed through `e9f0a1b2c3d4`. Upgrade from seeded `d8e9f0a1b2c3` preserved tenant,
  user, message, and T11 compliance records, installed five runtime tables with forced RLS and
  `USING`/`WITH CHECK`, and created no runtime rows during migration.
- Pre-suite runtime/security smoke passed `39`; post-suite logical guards passed `5`; post-suite
  RedisVL/generic Redis/Qdrant isolation passed `14`; migration-chain assertions passed `11`.
- The required full backend command collected `1747` tests and finished with `1746 passed`, `1
  failed`, `0 errors`, `4 skipped`, `81.61%` coverage, and `1987.61s (0:33:07)`. The sole failure is
  `tests/performance/test_performance.py::test_chat_endpoint_p95_under_500ms`: mocked authenticated
  `user_id=999` has no `users` row, so `conversations_user_id_fkey` rejects durable turn setup.
  Classification: `BACKEND_REGRESSION`; a focused compatibility fix and clean full rerun are needed.
- Human-review N/A is justified by no graph `interrupt()` continuation; outbox N/A is justified by
  no new T12 broker dispatch transaction. No production code changed during VERIFY.

State transition:

- T11 remains externally accepted `PASS`.
- T12 moves from `IN_PROGRESS / VERIFY_PENDING` to `NEEDS_EVIDENCE / VERIFY_BLOCKED` pending the
  focused compatibility fix and full-regression rerun.
- T13 remains `NOT_STARTED`; no later task was started.

# T12 Performance Fixture Fix Result

Completed: 2026-09-14

Status: `BLOCKED`

Execution Stage: `VERIFY_PENDING`

- The stale performance authenticated-user fixture is repaired: it persists a tenant-local
  `User` with the canonical async session setup and injects that generated ID into the mocked
  principal before the benchmark's timed request loop.
- Five sequential benchmark executions passed with P95 values from `210.94` to `232.32` ms;
  the performance module passed `4/4`, the focused T12 smoke passed `3/3`, and Ruff, format, and
  ty passed for the changed test file.
- The full backend regression remains pending by task instruction. T12 stays `BLOCKED /
  VERIFY_PENDING`; T13 stays `NOT_STARTED`. No production runtime, FK, authorization, or RLS
  architecture changed.

# T12 Final Regression Gate Result

Completed: 2026-09-14

Status: `BLOCKED`

Execution Stage: `VERIFY_PENDING`

- Final preflight and smoke passed: PostgreSQL, Redis, RabbitMQ, Qdrant, the performance module,
  chat P95 (`261.67` ms), duplicate submission, same-conversation concurrency, cancellation/stale
  result rejection, cross-tenant denial, and route inventory.
- The required full backend command collected `1751` tests and finished with `1716 passed`, `13
  failed`, `18 errors`, `4 skipped`, `81.28%` coverage, and `1882.19s (0:31:22)`. The performance
  benchmark passed; the `13` failures are real-LLM connection failures and the `18` setup errors
  are Windows pytest `tmp_path` permission failures. Classification: `ENVIRONMENT`.
- Post-suite guards passed (duplicate submission, cancelled late-result rejection, stale-result
  rejection, and route inventory). RedisVL/generic Redis cleanup passed `3/3`, Qdrant cleanup left
  zero test-scoped collections, RabbitMQ isolation remained on the dedicated `test_t12_verify`
  vhost, and Alembic remains the single head `e9f0a1b2c3d4`.
- No production implementation, user foreign key, authorization, RLS, migration, or T13 work was
  changed. T12 remains `BLOCKED / VERIFY_PENDING` until the environment blocker is removed and
  the full backend gate is rerun; T13 remains `NOT_STARTED`.

# T12 Environment Verification Result

Completed: 2026-09-14

Status: `AWAITING_ACCEPTANCE`

Execution Stage: `EXTERNAL_ACCEPTANCE_PENDING`

- The 13 previously failing nodes are all explicitly marked `requires_llm` and use the existing
  `real_llm` fixture. With dummy provider keys, the canonical `tests/conftest.py:280` policy
  excluded all `33` real-provider nodes without any tracked skip/xfail change; no public LLM call
  was attempted. Process provider variables were absent; the prior network attempts came from the
  non-dummy provider keys loaded by the developer `.env`.
- A unique current-user temp root passed create/write/rename/delete/child-directory preflight. All
  18 previously errored Windows `tmp_path` tests passed with `--basetemp` and no tracked fixture or
  production change.
- Compact T12 smoke passed `11` tests; the repaired chat benchmark passed with mean `195.73` ms,
  P95 `236.11` ms, and P99 `273.69` ms. The final hermetic backend command collected `1751`
  tests: `1714 passed`, `0 failed`, `0 errors`, `37 skipped`, `81.43%` coverage, elapsed
  `1652.38s (0:27:32)`. The `37` skips are the pre-existing `33` `requires_llm` cases plus `3`
  RabbitMQ and `1` Keycloak optional integration cases; their existing skip reasons were confirmed,
  and no new skip or xfail was introduced.
- Post-suite guards passed; RedisVL/generic Redis cleanup passed `3/3`, Qdrant cleanup left zero
  test-scoped collections, RabbitMQ remained isolated on `test_t12_verify`, the verification temp
  roots were removed, and Alembic remains the single head `e9f0a1b2c3d4`. No production code,
  migration, authorization, RLS, or T13 work changed.

State transition:

- T11 remains externally accepted `PASS`.
- T12 moves from `BLOCKED / VERIFY_PENDING` to `AWAITING_ACCEPTANCE /
  EXTERNAL_ACCEPTANCE_PENDING`; external acceptance is required and T12 is not marked `PASS`.
- T13 remains `NOT_STARTED`; no later task was started.

# T13 Final Verification Result

Completed: 2026-09-14

Status: `AWAITING_ACCEPTANCE`

Execution Stage: `EXTERNAL_ACCEPTANCE_PENDING`

- Infrastructure preflight passed for PostgreSQL, Redis, RabbitMQ, and Qdrant. A unique writable
  Windows basetemp passed filesystem operations and was removed after verification.
- Focused gateway/adapter checks passed (`41 passed`), post-suite guards passed (`14 passed`), and
  the authenticated T12 ConversationRuntime -> LangGraph -> ModelGateway -> Mock completion and
  cancellation smoke passed before and after the full suite.
- Hermetic full regression passed: `1792 collected`, `1755 passed`, `0 failed`, `0 errors`,
  `37 skipped`, `81.68%` coverage, `1909.49s (31:49)`. Skips are the existing `33` requires_llm,
  `3` RabbitMQ, and `1` Keycloak optional cases; no failure-hiding skip/xfail was added.
- No unexpected OpenAI/DashScope request occurred. Direct-SDK, client-control, secret/logging,
  route-inventory, Qdrant cleanup, Redis, RabbitMQ, Alembic, Ruff, format, ty, and lock checks pass.
  No production code or migration changed during VERIFY; optional real-provider smoke was not run.

State transition:

- T12 remains externally accepted `PASS`.
- T13 moves from `IN_PROGRESS / VERIFY_PENDING` to `AWAITING_ACCEPTANCE /
  EXTERNAL_ACCEPTANCE_PENDING`; it is not marked `PASS`.
- T14 remains `NOT_STARTED`.

# T14-T21 Workflow Transition Result

Completed: 2026-09-15

Status: `PASS_WITH_NOTES`

Execution Stage: `EXTERNAL_ACCEPTANCE_COMPLETE`

- T14-specific verification is complete; feature-only regressions = `0`.
- `DEFERRED_BASELINE_TEST_DEBT` remains recorded for OpenAI SDK cold-start deadline sensitivity
  and Celery fresh-process import deadline sensitivity. Both remain unresolved and do not block T15.
- Preflight confirmed clean `feat/t14-ai-failure-policy` at accepted HEAD
  `3c9c10bc25d7e77e5b53fccd36912a5150f2357b`; `git fetch origin --prune` completed.
- Documentation-only commit `8b0a48bab54d7423a51833a37f8f6ca1cee45e4d` established the
  T14-T21 workflow. The local branch is now `feat/t14-t21-enterprise-hardening`.
- Normal push configured `origin/feat/t14-t21-enterprise-hardening`; remote verification matched
  the exact commit above. The old remote `feat/t14-ai-failure-policy` was then removed normally.
- No force push was used, `main` was not modified, and no application code or tests changed.
- No backend tests were run for this documentation/workflow transition; testing was not required.
- T15 moves to `IN_PROGRESS / IMPLEMENT` on the same integration branch; T16 remains `NOT_STARTED`.

# T15 Implementation Start

Completed: 2026-09-15

Status: `IN_PROGRESS`

Execution Stage: `IMPLEMENT`

- Required T10 browser-session, T12 conversation-runtime, T13 model-gateway, and T14 failure-policy
  contracts were read before editing. The accepted cookie/CSRF/Origin/WebSocket/OIDC boundary is
  preserved; no backend security weakening is permitted.
- Frontend inventory found one existing generic HTTP client (`apiFetch`), one SSE path (`useChat`),
  one WebSocket hook (`useWebSocket`), server-authoritative Zustand auth state, and no Axios,
  EventSource, browser Bearer header, token storage, or token-bearing WebSocket URL path.
- The existing raw Web Vitals keepalive request is classified as a legitimate non-authenticated
  telemetry exception. Existing domain hooks already route through `apiFetch`.
- `/chat` already accepts `Idempotency-Key`; T12 already exposes durable logical cancellation.
  T15 will supply/reuse a domain key for one chat submission and will not invent keys for unrelated
  mutations. Backend correlation IDs remain server-owned, with safe response metadata capture.
- The two known protected-main baseline debts (OpenAI SDK cold-start and Celery fresh-process
  import deadlines) remain deferred and are not a T15 blocker.

State transition:

- T14 remains externally accepted `PASS_WITH_NOTES`.
- T15 is `IN_PROGRESS / IMPLEMENT`.
- T16 remains `NOT_STARTED`; no later task was started.

# T15 Implementation Closeout

Completed: 2026-09-15

Status: `IN_PROGRESS`

Execution Stage: `VERIFY_PENDING`

- Implemented one canonical browser HTTP transport with the accepted cookie-session contract,
  centralized session-bound CSRF, normalized/sanitized errors, explicit timeout and cancellation,
  bounded safe-read retry, idempotency-aware mutation policy, and safe correlation metadata.
- Customer SSE now uses the shared reader and one logical run state machine for `TURN_ACCEPTED`,
  deltas, metadata, terminal success/failure/cancel, local abort, and T12 logical cancellation.
  T14 provider fallback remains invisible as a second frontend request.
- The reusable WebSocket client strips token-like query parameters, relies on cookie/session and
  browser Origin behavior, upgrades to `wss` under HTTPS, and uses bounded close-code-aware
  reconnect with jitter. No backend replay/dedup contract was invented.
- TanStack Query retries are disabled to avoid double retry. Domain hooks, multipart uploads, and
  authenticated exports continue through the canonical transport; Web Vitals keepalive remains the
  only raw fetch exception and is unauthenticated telemetry.
- Frontend format check, lint, typecheck/build, `10` unit-test files (`47` tests), and two targeted
  Playwright security flows passed. Focused T10 browser-session/WebSocket guards passed (`22`), the
  route inventory guard passed, focused OIDC token-free browser tests passed (`3`), and
  `uv run alembic heads` reports `e9f0a1b2c3d4`.
- The first T10 smoke attempt exposed unavailable Compose host resolution. After starting only the
  needed local dependencies and using explicit IPv4 loopback for the isolated test database, the
  same focused guards passed. This was environment triage only; the full backend suite was not run.
- No backend application code, migration, database schema, or T16 work changed. The OpenAI SDK
  cold-start and Celery fresh-process import deadline sensitivities remain
  `DEFERRED_BASELINE_TEST_DEBT`, are not attributed to T15, and do not block T15.

State transition at implementation closeout:

- T14 remains externally accepted `PASS_WITH_NOTES`.
- T15 was `IN_PROGRESS / VERIFY_PENDING`; independent final verification is recorded below.
- T16 remains `NOT_STARTED`.

# T15 Verification Closeout

Completed: 2026-09-15

Status: `AWAITING_ACCEPTANCE`

Execution Stage: `EXTERNAL_ACCEPTANCE_PENDING`

- Final verification started from implementation head
  `93fde48077a998619ddce3c6c67b26abcde71f72` on
  `feat/t14-t21-enterprise-hardening`; the remote branch matched exactly and the working tree
  remained clean after verification.
- Production-source inventory confirms one canonical HTTP client (`apiFetch`), one shared SSE
  reader/customer stream, and one reusable cookie/origin WebSocket client. The only raw fetch
  exception is unauthenticated Web Vitals telemetry; OIDC remains a backend-owned redirect flow.
  No competing generic client, browser Bearer path, token persistence, or token URL path remains.
- Frontend gates passed: format check, lint, TypeScript/build, and Vitest (`10` files, `47` tests,
  `0` failures, `0` skips). Focused Chromium browser security flows passed (`2` tests).
- Focused T10 compatibility passed (`26` tests), covering cookie session, CSRF, Origin,
  logout/revocation, credential conflict, OIDC token-free callback, WebSocket query-token
  rejection, and the HTTP/WS route inventory. Focused T12/T14 compatibility passed (`7` tests)
  for logical cancellation, terminal uniqueness, provider fallback, post-visible no-fallback, and
  one normalized terminal failure.
- HTTP/SSE/WS retry, timeout, abort, normalized-error, idempotency, storage, URL, terminal-state,
  reconnect, and TanStack retry-ownership guards passed through the frontend unit suite. T14
  provider fallback remains one logical browser stream; no replay/dedup contract was fabricated.
- `uv run alembic heads` reports the single accepted head `e9f0a1b2c3d4`. No application code,
  backend route, migration, schema, or T16 work changed; the full backend regression was not run.
- No feature-hiding skip/xfail/todo was added. The protected-main OpenAI SDK cold-start and
  Celery fresh-process import deadline sensitivities remain
  `DEFERRED_BASELINE_TEST_DEBT`, are not attributed to T15, and do not block T15.

State transition:

- T14 remains externally accepted `PASS_WITH_NOTES`.
- T15 moves from `IN_PROGRESS / VERIFY_PENDING` to `AWAITING_ACCEPTANCE /
  EXTERNAL_ACCEPTANCE_PENDING`; external acceptance is required before `PASS`.
- T16 remains `NOT_STARTED` and cannot begin before T15 acceptance.
