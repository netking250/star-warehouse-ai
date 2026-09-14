"""Static regression guard for migrated critical publication paths."""

import ast
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _forbidden_calls(tree: ast.AST) -> list[str]:
    forbidden: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id == "dispatch_task":
            forbidden.append(node.func.id)
        if isinstance(node.func, ast.Attribute) and node.func.attr in {
            "delay",
            "apply_async",
            "send_task",
        }:
            forbidden.append(node.func.attr)
    return forbidden


def test_business_services_do_not_publish_directly_to_celery() -> None:
    """Keep refund business services dependent only on the outbox Port."""
    for relative_path in (
        "app/services/order_service.py",
        "app/services/admin_service.py",
    ):
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_task_modules = [
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.module is not None
            and node.module.startswith("app.tasks")
        ]
        assert imported_task_modules == [], relative_path
        assert _forbidden_calls(tree) == [], relative_path


def test_knowledge_write_routes_use_outbox_instead_of_direct_dispatch() -> None:
    """Keep knowledge creation and resync durable without banning other admin tasks."""
    source = (REPOSITORY_ROOT / "app/api/v1/admin/__init__.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {node.name: node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)}

    for function_name in ("upload_knowledge_document", "sync_knowledge_document_endpoint"):
        assert _forbidden_calls(functions[function_name]) == [], function_name
