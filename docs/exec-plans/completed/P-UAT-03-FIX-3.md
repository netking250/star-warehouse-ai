# P-UAT-03-FIX-3 - Business-Tool Routing and Refund Approval Boundary

## Status

- Task: `P-UAT-03-FIX-3`.
- Status: `AWAITING_ACCEPTANCE`.
- Execution stage: `EXTERNAL_ACCEPTANCE_PENDING`.
- Branch: `fix/uat03-runtime-side-effects`.
- Previous head: `76ac105435236eff3286a787201c5dc46dcd65e1`.
- Accepted main: `92a67ecec12d4cae00c31d70cf5a0b6664d393af`.
- Scope: logistics routing, refund application, risk audit, approval boundary, and idempotency.

## Frozen scope

- Repair only the reproduced E2 logistics route and E3/F1/F2 refund workflow boundary.
- Preserve user/order ownership, eligibility checks, transactional outbox semantics, and payment
  approval requirements.
- Preserve FIX-1/FIX-1B/FIX-2 behavior. Do not tune prompts, RAG, models, multi-turn memory, or
  general response style. Do not run the full P-UAT-03A suite.

## Reproduction status

Completed before the application fix through the real customer runtime with real Bailian:

- E2 (`查一下订单 SN649201 的物流。`) deterministically resolved to `ORDER/QUERY`, entered
  `order_agent`, and returned an order card without invoking logistics.
- E3 and both risk cases (`SN649201`, `SN649202`, `SN649203`) resolved to `ORDER/QUERY`, entered
  `order_agent`, and created no refund application or audit record.
- The root cause was the precedence/order of the existing deterministic rules: the concrete-order
  logistics wording did not match the narrow logistics rule, while the generic `查.*订单` and
  `SN\d+` rules won. The explicit after-sales wording likewise fell through to `SN\d+`.

## Implementation

The minimal implementation changes only the intent rule layer and its cache-precedence guard:

- Added narrow Chinese/English concrete-order logistics patterns and extracts `order_sn`.
- Added narrow Chinese/English explicit refund/return action patterns and sets the existing
  `AFTER_SALES/APPLY` plus `REFUND` tertiary action and order slot.
- Prevented a stale Redis classification from replacing those two high-signal deterministic
  transaction results.
- Added regression tests for rule precedence, stale-cache protection, and a known cross-user
  logistics order.

No router, agent, tool, service, eligibility, risk threshold, approval, prompt, model, RAG, or
schema code was changed.

## Verification status

Completed:

- Real Bailian fixed 7-case mini-suite: all seven `RUN_COMPLETED`; logistics entered `logistics`,
  the three refund cases entered `order_agent`, policy entered `policy_agent`, and complaint
  entered `complaint`.
- Tenant A database deltas: three `PENDING` refund applications (88, 1888, 2888), two
  `PENDING` audits (`MEDIUM`, `HIGH`), two `refund.notify_admin` outbox intents, zero
  `refund.process_payment` outbox/receipts, and one explicit complaint ticket.
- Focused tests: intent `82 passed, 7 skipped`; router/supervisor/logistics agent `21 passed`;
  LogisticsTool `4 passed`; OrderService refund entry/ownership `7 passed`; RefundService `12 passed`;
  refund tasks/outbox/audit `12 passed`; conversation idempotency `2 passed`; FIX-1 cache
  regression `1 passed`.
- Ruff check, Ruff format check, and ty passed for all changed Python files.

The exact disposable test database, temporary Redis container, and container test copy must be
removed before commit. The task finishes at `AWAITING_ACCEPTANCE / EXTERNAL_ACCEPTANCE_PENDING`;
Codex does not mark it `PASS`.

## Final closeout (2026-09-23)

Status: PASS. Earlier status and evidence above are preserved as historical observations.
