# Model Gateway Instructions

## Scope

This package owns provider-neutral chat-model contracts, configured use-case routes, capability
validation, provider request/response/stream translation, and the LangChain compatibility client.

## Invariants

- `ModelGateway.resolve()` returns ordered candidates; `invoke()` and `stream()` execute exactly one
  explicit candidate. Never add retries, automatic fallback, circuit state, health scoring, or
  degraded answers here; T14 owns failure policy.
- OpenAI/DashScope SDK imports and provider request objects stay under `providers/`. Application,
  graph, service, and runtime code consume normalized contracts or `GatewayChatModel`.
- Provider base URLs, API keys, route candidates, models, capabilities, and timeouts come only from
  trusted server configuration. Do not accept them from ordinary request payloads.
- Validate requested capabilities before provider I/O. Never silently discard tools, structured
  output, or streaming requirements.
- Every real call is async, explicitly time-bounded, and uses SDK `max_retries=0`. Preserve
  `asyncio.CancelledError` and normalize other provider failures through `ModelGatewayError`.
- T14 policy is the only model retry/fallback/circuit owner. It must remain provider-neutral,
  enforce finite attempt/deadline budgets, and never switch providers after a visible stream delta.
- Do not log prompts, responses, tool arguments, API keys, headers, or raw provider bodies.
- Mock behavior is deterministic and uses the same `ProviderAdapter` seam as real providers.

## Targeted Verification

```bash
uv run pytest tests/model_gateway -q
uv run ruff check app/model_gateway tests/model_gateway
uv run ty check --error-on-warning app/model_gateway tests/model_gateway
```
