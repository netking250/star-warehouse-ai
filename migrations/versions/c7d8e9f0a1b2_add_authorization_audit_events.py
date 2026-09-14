"""Add tenant authorization mutation audit evidence.

Revision ID: c7d8e9f0a1b2
Revises: b6c7d8e9f0a1
Create Date: 2026-09-13 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7d8e9f0a1b2"
down_revision: str | None = "b6c7d8e9f0a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RUNTIME_ROLE = "star_warehouse_runtime"
MAINTENANCE_ROLE = "star_warehouse_maintenance"
TENANT_SETTING = "app.current_tenant_id"
T09_TENANT_OWNED_TABLES: tuple[str, ...] = ("authorization_audit_events",)


def _policy_predicate() -> str:
    setting = f"NULLIF(current_setting('{TENANT_SETTING}', true), '')"
    return f"tenant_id = {setting} OR (current_user = '{MAINTENANCE_ROLE}' AND {setting} IS NULL)"


def upgrade() -> None:
    """Create authorization audit evidence with the accepted forced-RLS boundary."""
    op.create_table(
        "authorization_audit_events",
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=False),
        sa.Column("target_user_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("previous_role", sa.String(length=32), nullable=True),
        sa.Column("new_role", sa.String(length=32), nullable=True),
        sa.Column("previous_active", sa.Boolean(), nullable=True),
        sa.Column("new_active", sa.Boolean(), nullable=True),
        sa.Column("decision", sa.String(length=16), nullable=False, server_default="ALLOW"),
        sa.Column("reason_code", sa.String(length=64), nullable=False, server_default="ALLOW"),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_authorization_audit_events_tenant_id",
        "authorization_audit_events",
        ["tenant_id"],
    )
    op.create_index(
        "ix_authorization_audit_events_actor_user_id",
        "authorization_audit_events",
        ["actor_user_id"],
    )
    op.create_index(
        "ix_authorization_audit_events_target_user_id",
        "authorization_audit_events",
        ["target_user_id"],
    )
    op.create_index(
        "ix_authorization_audit_events_action",
        "authorization_audit_events",
        ["action"],
    )
    op.create_index(
        "ix_authorization_audit_events_correlation_id",
        "authorization_audit_events",
        ["correlation_id"],
    )

    table = '"authorization_audit_events"'
    op.execute(
        sa.text(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {table} "
            f"TO {RUNTIME_ROLE}, {MAINTENANCE_ROLE}"
        )
    )
    op.execute(
        sa.text(
            "GRANT USAGE, SELECT, UPDATE ON SEQUENCE authorization_audit_events_id_seq "
            f"TO {RUNTIME_ROLE}, {MAINTENANCE_ROLE}"
        )
    )
    op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    predicate = _policy_predicate()
    op.execute(
        sa.text(
            f"CREATE POLICY tenant_isolation ON {table} FOR ALL "
            f"TO {RUNTIME_ROLE}, {MAINTENANCE_ROLE} "
            f"USING ({predicate}) WITH CHECK ({predicate})"
        )
    )


def downgrade() -> None:
    """Remove tenant authorization mutation audit evidence."""
    op.drop_index(
        "ix_authorization_audit_events_correlation_id",
        table_name="authorization_audit_events",
    )
    op.drop_index("ix_authorization_audit_events_action", table_name="authorization_audit_events")
    op.drop_index(
        "ix_authorization_audit_events_target_user_id",
        table_name="authorization_audit_events",
    )
    op.drop_index(
        "ix_authorization_audit_events_actor_user_id",
        table_name="authorization_audit_events",
    )
    op.drop_index(
        "ix_authorization_audit_events_tenant_id",
        table_name="authorization_audit_events",
    )
    op.drop_table("authorization_audit_events")
