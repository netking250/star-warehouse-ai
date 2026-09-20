# P-UAT-03-PR-FIX

## Status

`AWAITING_ACCEPTANCE / EXTERNAL_ACCEPTANCE_PENDING`

Branch: `fix/uat03-runtime-side-effects`

PR: `#13`

Starting head: `98e64fb6e6a385105874be610be8a962ae2bd7ee`

Product acceptance: `P-UAT-03A-FINAL-RETEST PASS`

## Scope

Repair only the two blocking hosted failures on PR #13:

1. Scope `test_handle_refund_request_does_not_cross_user_order` to the protected target order and
   prove that an unrelated refund row does not affect the security assertion.
2. Resolve AnyIO from vulnerable `4.13.0` to compatible `>=4.14.2`, without broad dependency churn
   or a vulnerability suppression.

Do not modify production product, authorization, refund, tenant/RLS, AI, prompt, frontend, model,
provider, workflow, CI policy, or deployment behavior. Do not rerun the 30-case UAT. Do not merge
or enable auto-merge.

## Starting evidence

- Worktree: clean.
- Branch: `fix/uat03-runtime-side-effects`.
- Head: `98e64fb6e6a385105874be610be8a962ae2bd7ee`.
- Base: `main` at `92a67ecec12d4cae00c31d70cf5a0b6664d393af`.
- Hosted backend: `1946` collected, `1908` passed, `1` failed, `0` errors, `37` skipped,
  `82.23%` coverage.
- Sole failure: `tests/test_order_service.py::test_handle_refund_request_does_not_cross_user_order`.
- Hosted image scan: `critical=1`, `high=81`, `high_with_fix=37`; the critical finding is
  CVE-2026-63374 in AnyIO `4.13.0`, fixed in `4.14.2`.
- Production `OrderService` already scopes the order lookup to `order_sn + user_id`; no production
  authorization defect is demonstrated.

## Implementation plan

1. Add an unrelated order and refund record to the existing cross-user test, retain the protected
   target order object, and query only `RefundApplication.order_id == target_order.id` after the
   unauthorized attempt.
2. Inspect the resolved AnyIO/httpx/Starlette/FastAPI/OpenAI/LangChain graph, then upgrade only
   AnyIO in the lockfile. Add a project lower bound only if lock-only resolution is not durable.
3. Verify the focused test, order/refund suite, polluted-state behavior, Ruff, format, ty, lock
   integrity, frozen sync, installed version, application import/startup, Docker health where
   practical, and the repository Trivy image policy.
4. Review the old-head delta for product-source changes, create one focused commit, push normally
   to the existing branch, wait for new-head hosted checks, and leave PR #13 open and unmerged.

## Evidence log

- Recovery and mandatory pre-read completed before implementation.
- The AnyIO reverse graph includes Starlette/FastAPI, HTTPX, OpenAI, Uvicorn/watchfiles, Qdrant,
  LangGraph SDK, LangSmith, and Hugging Face consumers. Existing constraints admit the fixed release.
- Red proof: after adding one legitimate unrelated refund, the old global assertion failed with that
  exact row while `refund_flow_active` remained false.
- Green proof: the repaired target test passed with target-order refunds empty, requester refunds
  empty, and the unrelated refund still present.
- Focused order/refund suite: `27 passed`.
- Ruff check: PASS. Ruff format check: PASS (`477` files formatted). Ty with
  `--error-on-warning`: PASS.
- `uv lock --upgrade-package anyio` changed only AnyIO `4.13.0 -> 4.14.2`. `pyproject.toml` is
  unchanged. `uv lock --check` and `uv sync --frozen` pass; installed metadata reports `4.14.2`.
- CI-shaped image build: PASS. Image user: `appuser`. Application import reports AnyIO `4.14.2`.
- Docker startup/health: PASS within the hosted workflow's 90-second window. The first diagnostic
  attempt used host-style `localhost` for Qdrant inside the container; using the existing Compose
  network/service hostname reproduced the hosted topology and passed. Exact ephemeral smoke
  containers were removed afterward.
- Local Trivy `0.59.1` image-tar scan: `critical=0`, `high=81`, `high_with_fix=37`;
  CVE-2026-63374 count `0`; no suppression, waiver, allowlist, or policy change.
- One bounded real DashScope/Bailian connectivity request through the configured `qwen-plus`
  candidate returned `P_UAT_03_PR_FIX_OK`.
- Product application source diff: empty. No full backend suite or 30-case UAT rerun was performed.
- Remaining gate: create one focused commit, push normally to the existing PR branch, and wait for
  terminal new-head hosted checks. Do not merge or enable auto-merge.
