"""Tenant-scope all platform-owned tables.

Revision ID: b7c6d5e4f3a2
Revises: 9c8d7e6f5a4b
Create Date: 2026-08-10 00:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7c6d5e4f3a2"
down_revision: str | None = "9c8d7e6f5a4b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES: tuple[str, ...] = (
    "adversarial_test_runs",
    "agent_config_audit_logs",
    "agent_config_versions",
    "agent_configs",
    "alert_events",
    "alert_notifications",
    "alert_rules",
    "audit_logs",
    "complaint_tickets",
    "confidence_audits",
    "experiment_assignments",
    "experiment_metrics",
    "experiment_variants",
    "experiments",
    "graph_execution_logs",
    "graph_node_logs",
    "interaction_summaries",
    "knowledge_documents",
    "message_cards",
    "message_feedbacks",
    "multi_intent_decision_logs",
    "optimization_suggestions",
    "orders",
    "pii_audit_logs",
    "prompt_effect_reports",
    "quality_scores",
    "refund_applications",
    "review_tickets",
    "reviewer_metrics",
    "routing_rules",
    "shadow_test_results",
    "supervisor_decisions",
    "token_usage_logs",
    "user_facts",
    "user_preferences",
    "user_profiles",
)


def _ensure_non_unique_index(table_name: str, column_name: str) -> None:
    """Create or normalize a single-column non-unique index."""
    index_name = f"ix_{table_name}_{column_name}"
    indexes = {index["name"]: index for index in sa.inspect(op.get_bind()).get_indexes(table_name)}
    existing = indexes.get(index_name)
    if existing is not None and not existing["unique"]:
        return
    if existing is not None:
        op.drop_index(index_name, table_name=table_name)
    op.create_index(index_name, table_name, [column_name], unique=False)


def _ensure_unique_constraint(name: str, table_name: str, columns: list[str]) -> None:
    """Create a unique constraint unless the named constraint already exists."""
    constraints = {
        constraint["name"]
        for constraint in sa.inspect(op.get_bind()).get_unique_constraints(table_name)
    }
    if name not in constraints:
        op.create_unique_constraint(name, table_name, columns)


def upgrade() -> None:
    """Add tenant columns, indexes, and tenant-local uniqueness."""
    for table_name in TENANT_TABLES:
        column_names = {
            column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)
        }
        if "tenant_id" not in column_names:
            op.add_column(
                table_name,
                sa.Column(
                    "tenant_id", sa.String(length=64), server_default="default", nullable=False
                ),
            )
        else:
            op.alter_column(table_name, "tenant_id", server_default="default", nullable=False)
        _ensure_non_unique_index(table_name, "tenant_id")

    _ensure_non_unique_index("users", "username")
    _ensure_non_unique_index("users", "email")
    _ensure_non_unique_index("orders", "order_sn")
    _ensure_non_unique_index("agent_configs", "agent_name")

    _ensure_unique_constraint("uq_users_tenant_username", "users", ["tenant_id", "username"])
    _ensure_unique_constraint("uq_users_tenant_email", "users", ["tenant_id", "email"])
    _ensure_unique_constraint("uq_orders_tenant_order_sn", "orders", ["tenant_id", "order_sn"])
    _ensure_unique_constraint(
        "uq_agent_configs_tenant_name", "agent_configs", ["tenant_id", "agent_name"]
    )


def downgrade() -> None:
    """Restore global uniqueness and remove tenant columns."""
    op.drop_constraint("uq_agent_configs_tenant_name", "agent_configs", type_="unique")
    op.drop_constraint("uq_orders_tenant_order_sn", "orders", type_="unique")
    op.drop_constraint("uq_users_tenant_email", "users", type_="unique")
    op.drop_constraint("uq_users_tenant_username", "users", type_="unique")

    op.drop_index("ix_agent_configs_agent_name", table_name="agent_configs")
    op.drop_index("ix_orders_order_sn", table_name="orders")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_username", table_name="users")

    op.create_index("ix_agent_configs_agent_name", "agent_configs", ["agent_name"], unique=True)
    op.create_index("ix_orders_order_sn", "orders", ["order_sn"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    for table_name in reversed(TENANT_TABLES):
        op.drop_index(f"ix_{table_name}_tenant_id", table_name=table_name)
        op.drop_column(table_name, "tenant_id")
