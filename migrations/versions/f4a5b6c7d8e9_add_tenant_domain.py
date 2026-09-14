"""Add the operational tenant domain and remove implicit tenant defaults.

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-09-12 21:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f4a5b6c7d8e9"
down_revision: str | None = "e3f4a5b6c7d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_OWNED_TABLES: tuple[str, ...] = (
    "users",
    "orders",
    "refund_applications",
    "complaint_tickets",
    "message_cards",
    "knowledge_documents",
    "user_profiles",
    "user_preferences",
    "interaction_summaries",
    "user_facts",
    "agent_configs",
    "routing_rules",
    "agent_config_versions",
    "agent_config_audit_logs",
    "experiments",
    "experiment_variants",
    "experiment_assignments",
    "experiment_metrics",
    "confidence_audits",
    "message_feedbacks",
    "quality_scores",
    "shadow_test_results",
    "adversarial_test_runs",
    "graph_execution_logs",
    "graph_node_logs",
    "supervisor_decisions",
    "multi_intent_decision_logs",
    "prompt_effect_reports",
    "audit_logs",
    "pii_audit_logs",
    "review_tickets",
    "reviewer_metrics",
    "token_usage_logs",
    "optimization_suggestions",
    "alert_rules",
    "alert_events",
    "alert_notifications",
    "outbox_events",
    "task_execution_receipts",
)


def upgrade() -> None:
    """Create tenants, backfill identities, and remove default tenant writes."""
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="ACTIVE", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'SUSPENDED', 'DISABLED')",
            name="ck_tenants_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
    )
    op.create_index("ix_tenants_status", "tenants", ["status"])

    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_tables = set(inspector.get_table_names())
    for table_name in TENANT_OWNED_TABLES:
        if table_name not in existing_tables:
            continue
        table = sa.table(table_name, sa.column("tenant_id", sa.String(length=64)))
        tenant_ids = connection.execute(
            sa.select(table.c.tenant_id)
            .where(table.c.tenant_id.is_not(None), table.c.tenant_id != "")
            .distinct()
        ).scalars()
        for tenant_id in tenant_ids:
            connection.execute(
                sa.text(
                    "INSERT INTO tenants (id, slug, display_name, status) "
                    "VALUES (:tenant_id, :tenant_id, :tenant_id, 'ACTIVE') "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                {"tenant_id": tenant_id},
            )
        op.alter_column(table_name, "tenant_id", server_default=None, nullable=False)

    connection.execute(
        sa.text(
            "INSERT INTO tenants (id, slug, display_name, status) "
            "VALUES ('default', 'default', 'Local Bootstrap Tenant', 'ACTIVE') "
            "ON CONFLICT (id) DO NOTHING"
        )
    )


def downgrade() -> None:
    """Restore compatibility defaults and remove the tenant domain table."""
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())
    for table_name in TENANT_OWNED_TABLES:
        if table_name in existing_tables:
            op.alter_column(table_name, "tenant_id", server_default="default", nullable=False)
    op.drop_index("ix_tenants_status", table_name="tenants")
    op.drop_table("tenants")
