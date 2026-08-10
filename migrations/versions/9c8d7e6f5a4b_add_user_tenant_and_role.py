"""Add tenant namespace and RBAC role to users.

Revision ID: 9c8d7e6f5a4b
Revises: eda726e63e1d
Create Date: 2026-08-10 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9c8d7e6f5a4b"
down_revision: str | None = "eda726e63e1d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add backward-compatible tenant and role columns."""
    inspector = sa.inspect(op.get_bind())
    column_names = {column["name"] for column in inspector.get_columns("users")}
    if "tenant_id" not in column_names:
        op.add_column(
            "users",
            sa.Column("tenant_id", sa.String(length=64), server_default="default", nullable=False),
        )
    else:
        op.alter_column("users", "tenant_id", server_default="default", nullable=False)

    if "role" not in column_names:
        op.add_column(
            "users",
            sa.Column("role", sa.String(length=32), server_default="customer", nullable=False),
        )
    else:
        op.alter_column("users", "role", server_default="customer", nullable=False)

    index_names = {index["name"] for index in inspector.get_indexes("users")}
    if "ix_users_tenant_id" not in index_names:
        op.create_index("ix_users_tenant_id", "users", ["tenant_id"], unique=False)
    op.execute(sa.text("UPDATE users SET role = 'super_admin' WHERE is_admin = true"))


def downgrade() -> None:
    """Remove tenant and role columns."""
    op.drop_index("ix_users_tenant_id", table_name="users")
    op.drop_column("users", "role")
    op.drop_column("users", "tenant_id")
