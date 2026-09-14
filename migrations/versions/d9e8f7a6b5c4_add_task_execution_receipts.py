"""Add crash-recoverable task execution receipts.

Revision ID: d9e8f7a6b5c4
Revises: c8d7e6f5a4b3
Create Date: 2026-09-12 14:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d9e8f7a6b5c4"
down_revision: str | None = "c8d7e6f5a4b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create durable consumer receipt storage."""
    op.create_table(
        "task_execution_receipts",
        sa.Column("receipt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("handler", sa.String(length=192), nullable=False),
        sa.Column("idempotency_key", sa.String(length=192), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("claim_token", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("claim_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
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
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('PROCESSING', 'RETRYABLE', 'COMPLETED', 'TERMINAL')",
            name="ck_task_execution_receipts_status",
        ),
        sa.PrimaryKeyConstraint("receipt_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "handler",
            "idempotency_key",
            name="uq_task_execution_receipts_identity",
        ),
    )
    op.create_index(
        "ix_task_execution_receipts_tenant_id",
        "task_execution_receipts",
        ["tenant_id"],
    )
    op.create_index(
        "ix_task_execution_receipts_recovery",
        "task_execution_receipts",
        ["status", "claim_expires_at", "updated_at"],
    )


def downgrade() -> None:
    """Remove consumer receipt storage."""
    op.drop_index(
        "ix_task_execution_receipts_recovery",
        table_name="task_execution_receipts",
    )
    op.drop_index(
        "ix_task_execution_receipts_tenant_id",
        table_name="task_execution_receipts",
    )
    op.drop_table("task_execution_receipts")
