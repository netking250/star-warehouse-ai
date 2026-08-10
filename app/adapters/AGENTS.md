# AGENTS.md - Business Adapters

> **IMPORTANT**: Read the root [`AGENTS.md`](../../AGENTS.md) first for repo-wide rules.

## Overview

This package is the anti-corruption boundary between Agents/tools/services and authoritative business systems. Ports and canonical DTOs are stable application contracts; local, sandbox, mock, and production classes are replaceable infrastructure.

## Key Files

| Role | File |
|------|------|
| Canonical DTOs | `@app/adapters/contracts.py` |
| Port protocols | `@app/adapters/ports.py` |
| Normalized errors | `@app/adapters/errors.py` |
| Dependency composition | `@app/adapters/container.py` |
| Local infrastructure | `@app/adapters/local.py` |
| Production HTTP gateway | `@app/adapters/http.py` |
| Deterministic test modes | `@app/adapters/sandbox.py`, `@app/adapters/mock.py` |
| Timeout/retry/circuit breaker | `@app/adapters/resilience.py` |

## Invariants

- Propagate `tenant_id`, `user_id`, and `correlation_id` through `AdapterContext` on every call.
- Never accept tenant or user identity from untrusted tool slots or model output.
- Convert upstream responses to canonical DTOs and upstream failures to `AdapterError`.
- Retry only failures marked retryable; never retry authorization, validation, or conflict failures.
- Keep logs metadata-only. Do not log credentials, full upstream bodies, conversation history, or PII.
- Production endpoints require HTTPS unless the dedicated local-development override is explicitly enabled.
- Agents must not import adapters or infrastructure directly; tools/services receive Port dependencies.
- High-risk writes remain in their existing controlled service workflow until the V5 command boundary is implemented.

## Verification

```bash
uv run pytest tests/adapters tests/tools/
uv run ruff check app/adapters tests/adapters
uv run ty check --error-on-warning app/adapters tests/adapters
```

Update this file when Ports, adapter modes, resilience policies, or boundary rules change.
