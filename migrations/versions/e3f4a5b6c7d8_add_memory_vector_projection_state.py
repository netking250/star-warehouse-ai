"""Add authoritative memory vector projection state.

Revision ID: e3f4a5b6c7d8
Revises: d9e8f7a6b5c4
Create Date: 2026-09-12 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e3f4a5b6c7d8"
down_revision: str | None = "d9e8f7a6b5c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add version and tombstone fields to interaction summaries."""
    op.add_column(
        "interaction_summaries",
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "interaction_summaries",
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "interaction_summaries",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_interaction_summaries_vector_reconcile",
        "interaction_summaries",
        ["tenant_id", "is_deleted", "version"],
    )


def downgrade() -> None:
    """Remove interaction summary projection state."""
    op.drop_index(
        "ix_interaction_summaries_vector_reconcile",
        table_name="interaction_summaries",
    )
    op.drop_column("interaction_summaries", "deleted_at")
    op.drop_column("interaction_summaries", "is_deleted")
    op.drop_column("interaction_summaries", "version")
