"""Enable PostgreSQL row-level security for tenant-owned tables.

Revision ID: a5b6c7d8e9f0
Revises: f4a5b6c7d8e9
Create Date: 2026-09-12 23:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a5b6c7d8e9f0"
down_revision: str | None = "f4a5b6c7d8e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RUNTIME_ROLE = "star_warehouse_runtime"
MAINTENANCE_ROLE = "star_warehouse_maintenance"
POLICY_NAME = "tenant_isolation"
TENANT_SETTING = "app.current_tenant_id"

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


def _quoted(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _policy_predicate() -> str:
    setting = f"NULLIF(current_setting('{TENANT_SETTING}', true), '')"
    return f"tenant_id = {setting} OR (current_user = '{MAINTENANCE_ROLE}' AND {setting} IS NULL)"


def upgrade() -> None:
    """Create capability roles and protect the accepted T06 table inventory."""
    connection = op.get_bind()
    existing_tables = set(sa.inspect(connection).get_table_names())
    connection.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{RUNTIME_ROLE}') THEN
                    CREATE ROLE {RUNTIME_ROLE} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
                        NOINHERIT NOBYPASSRLS;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{MAINTENANCE_ROLE}') THEN
                    CREATE ROLE {MAINTENANCE_ROLE} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
                        NOINHERIT NOBYPASSRLS;
                END IF;
            END
            $$
            """
        )
    )
    connection.execute(
        sa.text(
            f"ALTER ROLE {RUNTIME_ROLE} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
            "NOINHERIT NOBYPASSRLS"
        )
    )
    connection.execute(
        sa.text(
            f"ALTER ROLE {MAINTENANCE_ROLE} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
            "NOINHERIT NOBYPASSRLS"
        )
    )
    capability_memberships = connection.execute(
        sa.text(
            "SELECT member.rolname, parent.rolname FROM pg_auth_members AS membership "
            "JOIN pg_roles AS member ON member.oid = membership.member "
            "JOIN pg_roles AS parent ON parent.oid = membership.roleid "
            "WHERE member.rolname IN (:runtime_role, :maintenance_role)"
        ),
        {"runtime_role": RUNTIME_ROLE, "maintenance_role": MAINTENANCE_ROLE},
    ).all()
    if capability_memberships:
        raise RuntimeError("RLS capability roles must not inherit or reach other roles")

    missing_tables = sorted(set(TENANT_OWNED_TABLES) - existing_tables)
    if missing_tables:
        raise RuntimeError(
            "Cannot enable RLS because tenant-owned tables are missing: "
            + ", ".join(missing_tables)
        )
    connection.execute(
        sa.text(f"GRANT USAGE ON SCHEMA public TO {RUNTIME_ROLE}, {MAINTENANCE_ROLE}")
    )
    if "tenants" in existing_tables:
        connection.execute(
            sa.text(f"GRANT SELECT ON TABLE tenants TO {RUNTIME_ROLE}, {MAINTENANCE_ROLE}")
        )
    connection.execute(
        sa.text(
            f"GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public "
            f"TO {RUNTIME_ROLE}, {MAINTENANCE_ROLE}"
        )
    )

    predicate = _policy_predicate()
    for table_name in TENANT_OWNED_TABLES:
        table = _quoted(table_name)
        connection.execute(
            sa.text(
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {table} "
                f"TO {RUNTIME_ROLE}, {MAINTENANCE_ROLE}"
            )
        )
        connection.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        connection.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
        connection.execute(sa.text(f"DROP POLICY IF EXISTS {POLICY_NAME} ON {table}"))
        connection.execute(
            sa.text(
                f"CREATE POLICY {POLICY_NAME} ON {table} FOR ALL "
                f"TO {RUNTIME_ROLE}, {MAINTENANCE_ROLE} "
                f"USING ({predicate}) WITH CHECK ({predicate})"
            )
        )


def downgrade() -> None:
    """Remove RLS and revoke tenant-table access while retaining cluster roles safely."""
    connection = op.get_bind()
    existing_tables = set(sa.inspect(connection).get_table_names())
    for table_name in reversed(TENANT_OWNED_TABLES):
        if table_name not in existing_tables:
            continue
        table = _quoted(table_name)
        connection.execute(sa.text(f"DROP POLICY IF EXISTS {POLICY_NAME} ON {table}"))
        connection.execute(sa.text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))
        connection.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))
        connection.execute(
            sa.text(
                f"REVOKE ALL PRIVILEGES ON TABLE {table} FROM {RUNTIME_ROLE}, {MAINTENANCE_ROLE}"
            )
        )
    if "tenants" in existing_tables:
        connection.execute(
            sa.text(
                f"REVOKE ALL PRIVILEGES ON TABLE tenants FROM {RUNTIME_ROLE}, {MAINTENANCE_ROLE}"
            )
        )
    connection.execute(
        sa.text(f"REVOKE USAGE ON SCHEMA public FROM {RUNTIME_ROLE}, {MAINTENANCE_ROLE}")
    )
