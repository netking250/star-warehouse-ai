# P-UAT-03-FINAL-FIX

## Status

`AWAITING_ACCEPTANCE / EXTERNAL_ACCEPTANCE_PENDING`

Branch: `fix/uat03-runtime-side-effects`

Accepted starting head: `49a97ffb7b5b0c04f8db6f8a3f9cf9128fb1573d`

## Scope

Repair only the preserved B3, C4, D2, D4, E2, E4, F1, and F2 failures from
P-UAT-03A-RETEST. Preserve tenant/user ownership, RLS, approval thresholds, payment-before-approval
prohibition, prompt-injection safety, durable-history isolation, model routes, Self-RAG, and retrieval
thresholds.

## Preserved reproduction

- B3 `我是东港仓发货，大概什么时候能出？`: fell through deterministic intent handling and was
  classified as `LOGISTICS`, prompting for an order number.
- C4 `Nova Desk 上门维修费用是多少？`: fell through deterministic intent handling and was
  classified as `AFTER_SALES`, prompting a return workflow.
- D2 `Nova Desk 的保修多久？` → `我买了26个月。` → `刚才说错了，是30个月。`: turn 3 was
  cancelled by the application SSE timeout at approximately 45 seconds with no streamed terminal
  event. The embedding fallback permits later call sites to repay a full timeout after an earlier
  same-process failure.
- D4 `Aurora Chair 退货窗口多久？` → `那如果是质量问题呢？`: the generic complaint query rule
  won because contextual policy continuation did not cover defect-only questions.
- E2 `查一下订单 SN649201 的物流。`: route was correct, but the alternating benchmark identity
  used user 1 while the order belongs to user 2.
- E4 `我收到的商品有质量问题，我想投诉并转人工客服。`: one authorized ticket was created,
  while deterministic response copy invented a 24-hour SLA and refund/replacement outcome.
- F1 `我想退货，订单 SN649202，商品有问题。`: the explicit refund rule did not recognize
  `我想`, so the generic order-number rule selected `ORDER/QUERY`.
- F2 `我想退货，订单 SN649203，商品有问题。`: same routing gap as F1, plus the benchmark used
  the non-owner identity.

## Implementation plan

1. Add exact-query failing tests, then narrowly repair informational dispatch/repair-fee semantics,
   defect-policy continuation, and explicit `我想退货` action routing.
2. Replace post-ticket complaint copy with confirmed ticket ID/status facts only.
3. Bound embedding failure reuse in one process and share the embedding adapter between conversation
   memory and policy retrieval so a turn does not repeatedly wait on a known provider outage; do not
   enlarge provider or SSE deadlines.
4. Add a disposable UAT support harness that chooses one transaction benchmark identity, asserts
   tenant/user/order ownership before model calls, and establishes the supported tenant-aware browser
   session without embedding credentials.
5. Run focused affected tests/static checks, the eight exact real-Bailian cases, controls, and manual
   customer UI proof. Do not run the final 30-case suite.

## Evidence log

- Pre-change branch/head/worktree: expected branch, accepted head, clean.
- Preserved P-UAT-03A-RETEST artifact recovered from OS temp; all exact prompts and failures traced.
- D2 durable rows show two cancelled turn-3 runs at the application 45-second boundary. The later
  confirmation run can complete when caches/provider timing are favorable, so the defect is timing
  accumulation rather than a deterministic graph deadlock.
- Browser login endpoint already accepts `tenant_id`; no production auth change is planned.
- Deterministic regression matrix: `223 passed`, `10 deselected` (optional real-provider tests),
  with no failures. Ruff check, Ruff format check, and ty all pass.
- UAT ownership preflight: benchmark `tenant-a/2`; SN649201, SN649202, and SN649203 are all
  `tenant-a/2`. OrderService, LocalOrderAdapter, LogisticsTool, tenant filters, and RLS were not
  weakened or bypassed.
- Focused real Bailian proof uses B3/C4/E2/E4/F1/F2 from the focused run and the post-fix D2/D4
  timing repeat. All eight cases have durable `RUN_COMPLETED`; `RUN_FAILED=0`, missing terminal=0,
  provider terminal errors=0, and unauthorized mutations=0.
- D2 completed twice after the timing repair. The final turns completed in `31.257s` and `24.042s`,
  used the corrected 30-month duration, and concluded that 30 months is outside the 28-month
  warranty. Historical durable runs prove the prior owner was the application SSE deadline:
  turn-three runs were `CANCELLED` at `43.004s` and `41.876s` inside the configured 45-second API
  boundary. No deadline was increased.
- D4 post-fix real answer states both the 17-day window and that the company pays return shipping
  for a verified quality problem. It remained `POLICY -> policy_agent` and created no complaint.
- F1 created refund `5` (`PENDING`) with audit `3` (`MEDIUM/PENDING`); F2 created refund `6`
  (`PENDING`) with audit `4` (`HIGH/PENDING`). Exactly two `refund.notify_admin` receipts exist,
  no payment outbox/receipt was created, and no new refund is `COMPLETED`.
- E4 created ticket `20` with status `open`; its answer reports only the ticket, status, and recorded
  submission. It contains no 24-hour/contact, refund, replacement, compensation, or outcome promise.
- Control proof completed A1/A5/A6, C1, D1, D3, E3, G1 tenant isolation, and G3 prompt injection.
  E3 reused the existing PENDING refund and created no duplicate.
- Frontend proof used the supported tenant-aware `/api/v1/browser/login` endpoint to establish the
  HttpOnly session for the same benchmark identity, then verified knowledge, no-answer, D2, logistics,
  refund idempotency, complaint, terminal loading state, feedback controls, and complete text. No
  application 4xx/5xx or console error occurred. OS-temp screenshots are under
  `C:/Users/11/AppData/Local/Temp/star-warehouse-ai-p-uat-03a-retest-20260919/screenshots`.
- The final 30-case retest was not run. No migration, PR, push, merge, model change, threshold change,
  approval redesign, broad prompt rewrite, or production-auth change occurred.

## Completion gate

Leave this task at `AWAITING_ACCEPTANCE`. External acceptance owns PASS. No PR or merge.

## Final closeout (2026-09-23)

Status: PASS. Earlier status and evidence above are preserved as historical observations.
