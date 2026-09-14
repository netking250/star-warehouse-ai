"""Add durable OIDC external identity bindings.

Revision ID: b6c7d8e9f0a1
Revises: a5b6c7d8e9f0
Create Date: 2026-09-13 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b6c7d8e9f0a1"
down_revision: str | None = "a5b6c7d8e9f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RUNTIME_ROLE = "star_warehouse_runtime"
MAINTENANCE_ROLE = "star_warehouse_maintenance"
POLICY_NAME = "tenant_isolation"
TENANT_SETTING = "app.current_tenant_id"
T08_TENANT_OWNED_TABLES: tuple[str, ...] = ("external_identities",)


def _policy_predicate() -> str:
    setting = f"NULLIF(current_setting('{TENANT_SETTING}', true), '')"
    return f"tenant_id = {setting} OR (current_user = '{MAINTENANCE_ROLE}' AND {setting} IS NULL)"


def upgrade() -> None:
    """Create the binding table and extend the accepted forced-RLS boundary."""
    op.create_table(
        "external_identities",
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("issuer", sa.String(length=512), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("email_at_link_time", sa.String(length=320), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "last_authenticated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("issuer", "subject", name="uq_external_identities_issuer_subject"),
    )
    op.create_index(
        "ix_external_identities_tenant_id", "external_identities", ["tenant_id"], unique=False
    )
    op.create_index(
        "ix_external_identities_user_id", "external_identities", ["user_id"], unique=False
    )

    table = '"external_identities"'
    op.execute(
        sa.text(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {table} "
            f"TO {RUNTIME_ROLE}, {MAINTENANCE_ROLE}"
        )
    )
    op.execute(
        sa.text(
            f"GRANT USAGE, SELECT, UPDATE ON SEQUENCE external_identities_id_seq "
            f"TO {RUNTIME_ROLE}, {MAINTENANCE_ROLE}"
        )
    )
    op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    predicate = _policy_predicate()
    op.execute(
        sa.text(
            f"CREATE POLICY {POLICY_NAME} ON {table} FOR ALL "
            f"TO {RUNTIME_ROLE}, {MAINTENANCE_ROLE} "
            f"USING ({predicate}) WITH CHECK ({predicate})"
        )
    )


def downgrade() -> None:
    """Remove the external identity binding table."""
    op.drop_index("ix_external_identities_user_id", table_name="external_identities")
    op.drop_index("ix_external_identities_tenant_id", table_name="external_identities")
    op.drop_table("external_identities")
