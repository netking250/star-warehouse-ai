# Conversation Runtime Instructions

## Scope

This package owns durable conversation, turn, run, tool-result, cancellation, recovery, and
ordered lifecycle-event semantics around the existing AI graph.

## Invariants

- `ConversationRuntime` is the business/API seam; only executor adapters may import LangGraph.
- PostgreSQL owns durable runtime truth. Redis/checkpoints and token chunks are transient.
- Every command is bound to trusted tenant and user identity; knowing a run ID is never authority.
- Keep `conversation_id`, `turn_id`, and `run_id` distinct and validate all three for asynchronous
  result acceptance.
- Mutating transitions use the centralized state machine, a transaction-scoped conversation lock,
  and optimistic revisions; terminal states never reopen.
- Infrastructure may deliver at least once, but database uniqueness must preserve one logical turn,
  event, tool result, and terminal assistant message.
- Logical cancellation rejects late results even when provider or tool execution cannot be stopped.
- Add new tenant runtime tables to the T07 inventory, forced RLS migration, and T11 classification
  registry in the same change.

## Targeted Verification

```bash
uv run pytest tests/conversation
uv run pytest tests/test_chat_api.py tests/authorization/test_authorization.py
uv run pytest tests/integration/test_postgres_rls.py::test_tenant_inventory_has_forced_all_command_policies
uv run ruff check app/conversation tests/conversation
uv run ty check --error-on-warning app/conversation tests/conversation
```
