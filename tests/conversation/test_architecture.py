"""Structural guards for the conversation runtime boundary."""

import ast
from pathlib import Path

from app.authorization.policy import Scope
from app.authorization.route_inventory import (
    HTTP_ROUTE_POLICIES,
    RouteClassification,
)

_API_FILES = (
    Path("app/api/v1/chat.py"),
    Path("app/api/v1/conversation.py"),
)
_RUNTIME_ROUTES = frozenset(
    {
        ("GET", "/api/v1/conversations/{conversation_id}/runs/{run_id}"),
        ("GET", "/api/v1/conversations/{conversation_id}/runs/{run_id}/events"),
        ("POST", "/api/v1/conversations/{conversation_id}/runs/{run_id}/cancel"),
    }
)


def test_api_transport_does_not_import_langgraph_internals() -> None:
    for path in _API_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        imports.extend(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        assert not any(name == "langgraph" or name.startswith("langgraph.") for name in imports)
        assert not any(name.startswith("app.graph") for name in imports)


def test_runtime_control_routes_are_tenant_scoped_chat_capabilities() -> None:
    for route in _RUNTIME_ROUTES:
        policy = HTTP_ROUTE_POLICIES[route]
        assert policy.classification is RouteClassification.TENANT_SCOPE_REQUIRED
        assert policy.authorization is not None
        assert policy.authorization.scopes == frozenset({Scope.CHAT_USE})


def test_repository_has_no_langgraph_interrupt_resume_runtime_to_preserve() -> None:
    graph_sources = "\n".join(
        path.read_text(encoding="utf-8") for path in Path("app/graph").glob("*.py")
    )
    assert "interrupt(" not in graph_sources
