"""Add the durable tenant-owned conversation runtime.

Revision ID: e9f0a1b2c3d4
Revises: d8e9f0a1b2c3
Create Date: 2026-09-14 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e9f0a1b2c3d4"
down_revision: str | None = "d8e9f0a1b2c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RUNTIME_ROLE = "star_warehouse_runtime"
MAINTENANCE_ROLE = "star_warehouse_maintenance"
TENANT_SETTING = "app.current_tenant_id"
T12_TENANT_OWNED_TABLES: tuple[str, ...] = (
    "conversations",
    "conversation_turns",
    "conversation_runs",
    "conversation_runtime_events",
    "conversation_tool_executions",
)


def _policy_predicate() -> str:
    setting = f"NULLIF(current_setting('{TENANT_SETTING}', true), '')"
    return f"tenant_id = {setting} OR (current_user = '{MAINTENANCE_ROLE}' AND {setting} IS NULL)"


def _enable_rls(table_name: str) -> None:
    table = f'"{table_name}"'
    predicate = _policy_predicate()
    op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"CREATE POLICY tenant_isolation ON {table} FOR ALL "
            f"TO {RUNTIME_ROLE}, {MAINTENANCE_ROLE} "
            f"USING ({predicate}) WITH CHECK ({predicate})"
        )
    )


def _timestamps() -> tuple[sa.Column[object], sa.Column[object]]:
    return (
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )


def upgrade() -> None:
    """Create the additive T12 runtime schema and secure it immediately."""
    created_at, updated_at = _timestamps()
    op.create_table(
        "conversations",
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active_run_id", sa.String(length=36), nullable=True),
        created_at,
        updated_at,
        sa.CheckConstraint("revision >= 0", name="ck_conversations_revision_nonnegative"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "conversation_id", name="uq_conversations_identity"),
    )
    created_at, updated_at = _timestamps()
    op.create_table(
        "conversation_turns",
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("turn_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=192), nullable=False),
        sa.Column("current_run_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="PENDING"),
        created_at,
        updated_at,
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "turn_id", name="uq_conversation_turns_identity"),
        sa.UniqueConstraint(
            "tenant_id",
            "conversation_id",
            "idempotency_key",
            name="uq_conversation_turns_submission",
        ),
    )
    created_at, updated_at = _timestamps()
    op.create_table(
        "conversation_runs",
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("turn_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="PENDING"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("conversation_revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_event_sequence", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("final_message_id", sa.Integer(), nullable=True),
        sa.Column("failure_category", sa.String(length=64), nullable=True),
        sa.Column("failure_metadata", sa.JSON(), nullable=True),
        created_at,
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        updated_at,
        sa.CheckConstraint("attempt >= 1", name="ck_conversation_runs_attempt_positive"),
        sa.CheckConstraint("revision >= 0", name="ck_conversation_runs_revision_nonnegative"),
        sa.CheckConstraint(
            "conversation_revision >= 0",
            name="ck_conversation_runs_conversation_revision_nonnegative",
        ),
        sa.CheckConstraint(
            "next_event_sequence >= 1",
            name="ck_conversation_runs_event_sequence_positive",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'WAITING_TOOL', 'WAITING_HUMAN', "
            "'COMPLETED', 'FAILED', 'CANCELLED')",
            name="ck_conversation_runs_status",
        ),
        sa.ForeignKeyConstraint(["final_message_id"], ["message_cards.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "run_id", name="uq_conversation_runs_identity"),
        sa.UniqueConstraint("tenant_id", "turn_id", "attempt", name="uq_conversation_runs_attempt"),
    )
    op.create_table(
        "conversation_runtime_events",
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=128), nullable=False),
        sa.Column("turn_id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_key", sa.String(length=192), nullable=False),
        sa.Column("event_type", sa.String(length=48), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("sequence >= 1", name="ck_runtime_events_sequence_positive"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "event_id", name="uq_runtime_events_identity"),
        sa.UniqueConstraint("tenant_id", "run_id", "sequence", name="uq_runtime_events_sequence"),
        sa.UniqueConstraint("tenant_id", "run_id", "event_key", name="uq_runtime_events_key"),
    )
    created_at, updated_at = _timestamps()
    op.create_table(
        "conversation_tool_executions",
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tool_execution_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=128), nullable=False),
        sa.Column("turn_id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tool_name", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=192), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="REQUESTED"),
        sa.Column("expected_run_revision", sa.Integer(), nullable=False),
        sa.Column("result_delivery_id", sa.String(length=192), nullable=True),
        sa.Column("result_payload", sa.JSON(), nullable=True),
        sa.Column("failure_category", sa.String(length=64), nullable=True),
        created_at,
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        updated_at,
        sa.CheckConstraint(
            "expected_run_revision >= 0",
            name="ck_tool_executions_expected_revision_nonnegative",
        ),
        sa.CheckConstraint(
            "status IN ('REQUESTED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED')",
            name="ck_tool_executions_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "tool_execution_id", name="uq_tool_executions_identity"),
        sa.UniqueConstraint(
            "tenant_id", "run_id", "idempotency_key", name="uq_tool_executions_idempotency"
        ),
    )

    op.add_column("message_cards", sa.Column("conversation_id", sa.String(128), nullable=True))
    op.add_column("message_cards", sa.Column("turn_id", sa.String(36), nullable=True))
    op.add_column("message_cards", sa.Column("run_id", sa.String(36), nullable=True))
    op.add_column("message_cards", sa.Column("logical_message_id", sa.String(128), nullable=True))
    op.create_unique_constraint(
        "uq_message_cards_logical_message",
        "message_cards",
        ["tenant_id", "logical_message_id"],
    )

    indexes: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
        "conversations": (
            ("ix_conversations_tenant_id", ("tenant_id",)),
            ("ix_conversations_user_id", ("user_id",)),
            ("ix_conversations_active_run_id", ("active_run_id",)),
            ("ix_conversations_owner", ("tenant_id", "user_id", "updated_at")),
        ),
        "conversation_turns": (
            ("ix_conversation_turns_tenant_id", ("tenant_id",)),
            ("ix_conversation_turns_user_id", ("user_id",)),
            ("ix_conversation_turns_current_run_id", ("current_run_id",)),
            ("ix_conversation_turns_status", ("status",)),
            (
                "ix_conversation_turns_order",
                ("tenant_id", "conversation_id", "created_at"),
            ),
        ),
        "conversation_runs": (
            ("ix_conversation_runs_tenant_id", ("tenant_id",)),
            ("ix_conversation_runs_user_id", ("user_id",)),
            ("ix_conversation_runs_correlation_id", ("correlation_id",)),
            ("ix_conversation_runs_status", ("status",)),
            (
                "ix_conversation_runs_recovery",
                ("tenant_id", "status", "updated_at"),
            ),
            (
                "ix_conversation_runs_conversation",
                ("tenant_id", "conversation_id", "created_at"),
            ),
        ),
        "conversation_runtime_events": (
            ("ix_conversation_runtime_events_tenant_id", ("tenant_id",)),
            ("ix_conversation_runtime_events_event_type", ("event_type",)),
            ("ix_conversation_runtime_events_correlation_id", ("correlation_id",)),
            ("ix_runtime_events_replay", ("tenant_id", "run_id", "sequence")),
        ),
        "conversation_tool_executions": (
            ("ix_conversation_tool_executions_tenant_id", ("tenant_id",)),
            ("ix_conversation_tool_executions_user_id", ("user_id",)),
            ("ix_conversation_tool_executions_status", ("status",)),
            ("ix_tool_executions_run", ("tenant_id", "run_id", "created_at")),
        ),
    }
    for table_name, table_indexes in indexes.items():
        for index_name, columns in table_indexes:
            op.create_index(index_name, table_name, list(columns))
        op.execute(
            sa.text(
                f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE "{table_name}" '
                f"TO {RUNTIME_ROLE}, {MAINTENANCE_ROLE}"
            )
        )
        op.execute(
            sa.text(
                f'GRANT USAGE, SELECT ON SEQUENCE "{table_name}_id_seq" '
                f"TO {RUNTIME_ROLE}, {MAINTENANCE_ROLE}"
            )
        )
        _enable_rls(table_name)

    for column_name in ("conversation_id", "turn_id", "run_id"):
        op.create_index(f"ix_message_cards_{column_name}", "message_cards", [column_name])


def downgrade() -> None:
    """Remove the T12 runtime schema and nullable message identity extensions."""
    for column_name in ("run_id", "turn_id", "conversation_id"):
        op.drop_index(f"ix_message_cards_{column_name}", table_name="message_cards")
    op.drop_constraint("uq_message_cards_logical_message", "message_cards", type_="unique")
    for column_name in ("logical_message_id", "run_id", "turn_id", "conversation_id"):
        op.drop_column("message_cards", column_name)
    for table_name in reversed(T12_TENANT_OWNED_TABLES):
        op.drop_table(table_name)
