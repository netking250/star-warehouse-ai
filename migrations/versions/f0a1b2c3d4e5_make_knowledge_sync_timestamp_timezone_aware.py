"""Make knowledge synchronization timestamps timezone-aware.

Revision ID: f0a1b2c3d4e5
Revises: e9f0a1b2c3d4
Create Date: 2026-09-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f0a1b2c3d4e5"
down_revision: str | None = "e9f0a1b2c3d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Interpret legacy naive values as UTC and store future UTC instants safely."""
    op.alter_column(
        "knowledge_documents",
        "last_synced_at",
        existing_type=sa.DateTime(timezone=False),
        type_=sa.DateTime(timezone=True),
        postgresql_using="last_synced_at AT TIME ZONE 'UTC'",
        existing_nullable=True,
    )


def downgrade() -> None:
    """Convert timezone-aware values back to naive UTC timestamps."""
    op.alter_column(
        "knowledge_documents",
        "last_synced_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(timezone=False),
        postgresql_using="last_synced_at AT TIME ZONE 'UTC'",
        existing_nullable=True,
    )
