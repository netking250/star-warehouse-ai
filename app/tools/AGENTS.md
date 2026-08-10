# AGENTS.md - Tools

> **IMPORTANT**: Read the root [`AGENTS.md`](../../AGENTS.md) first for repo-wide rules.

## Maintenance Contract

- This file is a living document for the agent tool layer.
- Update this file in the same PR when adding new tools, changing the registry, or modifying tool conventions.

## Read Order

1. Read the root [`AGENTS.md`](../../AGENTS.md) for repo-wide rules, commands, and routing.
2. Read this file for tool-specific guidance.

## Overview

The tool layer provides a unified interface for agents to perform I/O operations. Each tool inherits from `BaseTool` and exposes an `async execute(state) -> ToolResult` method. Tools are registered in `ToolRegistry` for dynamic discovery.

## Key Files

| Role | File | Notes |
|------|------|-------|
| Base class | `@app/tools/base.py` | `BaseTool` ABC; `ToolResult` (Pydantic BaseModel) |
| Tool registry | `@app/tools/registry.py` | `ToolRegistry` for dynamic tool discovery |
| Product tool | `@app/tools/product_tool.py` | ProductPort-backed catalog retrieval |
| Cart tool | `@app/tools/cart_tool.py` | CartPort-backed low-risk cart operations |
| Complaint tool | `@app/tools/complaint_tool.py` | Complaint ticket creation and management |
| Payment tool | `@app/tools/payment_tool.py` | Payment/Invoice/Order/Refund Port projections |
| Logistics tool | `@app/tools/logistics_tool.py` | LogisticsPort-backed tracking |
| Account tool | `@app/tools/account_tool.py` | IdentityPort-backed account projection |

## Commands

```bash
# Run tool module tests
uv run pytest tests/tools/
```

## Code Style

General Python rules are defined in the root `AGENTS.md`. Tool-specific conventions:

- **Type hints**: Mandatory on all `BaseTool` subclass methods and `ToolResult` fields.
- **Docstrings**: Google-style docstrings for all public tool classes and `execute()` methods.
- **No sync I/O**: Tools must not perform synchronous blocking calls; all external access is `async`.
- **Business boundary**: Tools access authoritative business data only through protocols in `@app/adapters/ports.py`.
- **Error handling**: Tools must catch specific exceptions and return `ToolResult(output={"error": str(e)}, confidence=0.0)` rather than raising.

## Testing Patterns

- Mock external dependencies (Redis, Qdrant, database) in tool tests.
- Verify `ToolResult` structure for both success and failure cases.
- Test `ToolRegistry` discovery and registration.
- New tool → new test file under `tests/tools/`.

## Conventions

- **Unified entry**: All `BaseTool` subclasses must implement `async execute(self, state) -> ToolResult`.
- **Registry registration**: Tools must register themselves in `ToolRegistry` for agent discovery.
- **User isolation**: All order/refund/cart/account queries must filter by `user_id`.
- **Return contract**: `ToolResult` must include `output` (dict), `confidence` (float, default 1.0), and `source` (str, default "tool").

## Anti-Patterns

- **Direct DB access from agents**: Agents should use tools, not access the database directly.
- **Direct infrastructure access**: Tools must not call SQL, Redis, Qdrant, ERP/OMS, payment, or logistics clients directly; implement that I/O in an Adapter.
- **Unregistered tools**: Tools that are not registered in `ToolRegistry` cannot be discovered by agents.
- **Synchronous I/O in tools**: All external calls must be `async` to avoid blocking the event loop.

## Related Files

- `@app/agents/AGENTS.md` — Agent fleet that consumes these tools.
- `@app/agents/base.py` — `BaseAgent` delegates I/O to the tool layer.
