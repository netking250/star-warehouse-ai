"""Add the transactional outbox.

Revision ID: c8d7e6f5a4b3
Revises: b7c6d5e4f3a2
Create Date: 2026-09-11 20:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c8d7e6f5a4b3"
down_revision: str | None = "b7c6d5e4f3a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create durable sanitized task-envelope storage for the relay."""
    op.create_table(
        "outbox_events",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("aggregate_type", sa.String(length=64), nullable=False),
        sa.Column("aggregate_id", sa.String(length=128), nullable=False),
        sa.Column("task_name", sa.String(length=192), nullable=False),
        sa.Column("envelope", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("idempotency_key", sa.String(length=192), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="PENDING", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
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
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("claim_token", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("claim_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDING', 'PUBLISHING', 'PUBLISHED')",
            name="ck_outbox_events_status",
        ),
        sa.PrimaryKeyConstraint("event_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_outbox_events_tenant_idempotency",
        ),
    )
    op.create_index("ix_outbox_events_tenant_id", "outbox_events", ["tenant_id"])
    op.create_index(
        "ix_outbox_events_relay_eligible",
        "outbox_events",
        ["status", "available_at", "created_at"],
    )


def downgrade() -> None:
    """Remove the transactional outbox table."""
    op.drop_index("ix_outbox_events_relay_eligible", table_name="outbox_events")
    op.drop_index("ix_outbox_events_tenant_id", table_name="outbox_events")
    op.drop_table("outbox_events")
