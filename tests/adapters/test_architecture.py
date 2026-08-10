"""Architecture guardrails for Agent-to-business-system boundaries."""

from pathlib import Path


def test_migrated_tools_do_not_call_infrastructure_clients_directly() -> None:
    root = Path(__file__).parents[2]
    migrated_tools = [
        "account_tool.py",
        "cart_tool.py",
        "logistics_tool.py",
        "payment_tool.py",
        "product_tool.py",
    ]
    forbidden_calls = (".exec(", ".query_points(", ".setex(", ".execute(")

    for filename in migrated_tools:
        source = (root / "app" / "tools" / filename).read_text(encoding="utf-8")
        for forbidden in forbidden_calls:
            assert forbidden not in source, f"{filename} bypasses an adapter with {forbidden}"
