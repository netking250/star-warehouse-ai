"""Structural guardrails for the provider SDK seam."""

import ast
from pathlib import Path

from app.model_gateway.factory import create_model_client
from app.model_gateway.langchain import GatewayChatModel

_PROVIDER_MODULES = frozenset({"openai", "langchain_openai", "dashscope"})
_APP_ROOT = Path(__file__).resolve().parents[2] / "app"
_APPROVED_PROVIDER_DIRECTORY = _APP_ROOT / "model_gateway" / "providers"


def test_production_provider_sdk_imports_are_confined_to_adapters() -> None:
    violations: list[str] = []
    for path in _APP_ROOT.rglob("*.py"):
        if path.is_relative_to(_APPROVED_PROVIDER_DIRECTORY):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            module: str | None = None
            if isinstance(node, ast.ImportFrom):
                module = node.module
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".", maxsplit=1)[0] in _PROVIDER_MODULES:
                        module = alias.name
                        break
            if module is not None and module.split(".", maxsplit=1)[0] in _PROVIDER_MODULES:
                violations.append(str(path.relative_to(_APP_ROOT)))
                break

    assert violations == []


def test_legacy_factory_returns_gateway_client_not_provider_sdk_object() -> None:
    client = create_model_client("default_chat")

    assert isinstance(client, GatewayChatModel)
