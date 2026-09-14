# Dynamic Model Gateway

T13 introduces one model interface between application code and remote chat providers:

```text
ConversationRuntime / LangGraph / agents / AI services
                         |
                    ModelGateway
                         |
                  explicit ModelCandidate
                         |
                 ProviderAdapter
                 |       |       |
              OpenAI  DashScope  Mock
```

## Interface

`ModelRequest`, `ModelResponse`, and `ModelStreamEvent` are provider-neutral. They cover the
capabilities used by the repository: chat, streaming, function tools, and structured output.
Responses expose the actual provider/model, safe request ID, finish reason, latency, normalized tool
calls, and provider-reported token usage. Missing usage is left missing; token counts are not
fabricated.

`GatewayChatModel` adapts this interface to the existing LangChain/LangGraph call sites. Provider
SDK response objects never cross that seam into agents, runtime, HTTP, or WebSocket code. The
user-visible graph path copies only safe provider/model/usage metadata into T12 terminal metadata.

## Route configuration

`Settings.MODEL_ROUTES` is restart-on-change operator configuration. Current route aliases are
`default_chat`, `intent`, `structured`, `evaluation`, `shadow`, `rewrite`, `summarization`, and
`safety`. Each route contains an ordered candidate list with explicit provider, model, tested
capabilities, and timeout. The defaults put OpenAI first and DashScope second where both implement
the required capability. Provider base URLs are separate trusted settings; ordinary API requests
cannot submit a provider endpoint. Configured URLs must be HTTP(S), include a host, and cannot
embed credentials, queries, or fragments.

Resolution is capability-aware. A tools, structured-output, or streaming request is rejected before
external I/O when the chosen candidate cannot preserve that requirement. Unknown routes/providers,
empty models/routes, unsupported capability declarations, and invalid timeouts fail during registry
construction or resolution.

## Provider adapters

The OpenAI adapter uses the official async client. The DashScope adapter uses its documented
OpenAI-compatible endpoint through the same client protocol. Both set explicit timeouts and
`max_retries=0`, normalize text/tool/structured/streaming output, preserve coroutine cancellation,
and map failures to the stable categories `AUTHENTICATION`, `RATE_LIMIT`, `TIMEOUT`, `CONNECTION`,
`BAD_REQUEST`, `UNSUPPORTED_CAPABILITY`, `PROVIDER_UNAVAILABLE`, `INVALID_RESPONSE`, and `UNKNOWN`.
Safe diagnostics exclude API keys, authorization headers, prompts, responses, and raw provider
bodies.

The Mock provider is deterministic, offline, and supports completion, streaming chunks, tool calls,
structured results, latency, normalized failure/timeout injection, and malformed-response
injection through the same provider interface.

## Failure-policy ownership

T13 never retries a model call and never invokes the next route candidate after a failure. Route
order makes fallback possible, but T14 exclusively owns retry count/backoff, automatic fallback,
circuit breaking, provider health, failure budgets, and degraded-answer strategy.

## Test hermeticity and secrets

Offline adapter tests exercise the real translation code with `httpx.MockTransport`; gateway tests
use the Mock provider. Public internet is not required. Existing tests marked `requires_llm` still
use `real_llm`, but credentials alone are insufficient: operators must explicitly set
`RUN_REAL_LLM_TESTS=1`. Missing or placeholder credentials still skip cleanly. Real-provider tests
are optional smoke evidence and must use trivial, non-sensitive prompts.

Provider credentials remain `SecretStr` server settings. They are never stored in frontend state,
runtime events, audit metadata, logs, or business tables. No persistence or migration is added by
T13.
