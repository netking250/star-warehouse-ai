"""Add compliance lifecycle, immutable audit, and sensitive export approval.

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
Create Date: 2026-09-14 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d8e9f0a1b2c3"
down_revision: str | None = "c7d8e9f0a1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RUNTIME_ROLE = "star_warehouse_runtime"
MAINTENANCE_ROLE = "star_warehouse_maintenance"
TENANT_SETTING = "app.current_tenant_id"
T11_TENANT_OWNED_TABLES: tuple[str, ...] = (
    "compliance_audit_events",
    "approval_requests",
    "sensitive_export_artifacts",
)
IMMUTABLE_AUDIT_TABLES: tuple[str, ...] = (
    "authorization_audit_events",
    "compliance_audit_events",
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


def upgrade() -> None:
    """Create additive T11 structures without deleting historical data."""
    op.create_table(
        "compliance_audit_events",
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("actor_type", sa.String(length=24), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_reference", sa.String(length=128), nullable=True),
        sa.Column("outcome", sa.String(length=24), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("event_metadata", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "approval_requests",
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("operation_type", sa.String(length=64), nullable=False),
        sa.Column("requester_user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("operation_payload_hash", sa.String(length=64), nullable=False),
        sa.Column("operation_parameters", sa.JSON(), nullable=False),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approver_user_id", sa.Integer(), nullable=True),
        sa.Column("decision_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.ForeignKeyConstraint(["requester_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["approver_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "sensitive_export_artifacts",
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("approval_request_id", sa.String(length=36), nullable=False),
        sa.Column("operation_payload_hash", sa.String(length=64), nullable=False),
        sa.Column("filename", sa.String(length=160), nullable=False),
        sa.Column("media_type", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["approval_request_id"], ["approval_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("approval_request_id", name="uq_sensitive_export_approval"),
    )

    indexed_columns = {
        "compliance_audit_events": (
            "tenant_id",
            "event_type",
            "actor_user_id",
            "target_type",
            "outcome",
            "correlation_id",
        ),
        "approval_requests": (
            "tenant_id",
            "operation_type",
            "requester_user_id",
            "status",
            "operation_payload_hash",
            "expires_at",
            "approver_user_id",
            "correlation_id",
        ),
        "sensitive_export_artifacts": ("tenant_id", "approval_request_id", "expires_at"),
    }
    for table_name, columns in indexed_columns.items():
        for column in columns:
            op.create_index(f"ix_{table_name}_{column}", table_name, [column])
        op.execute(
            sa.text(
                f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE "{table_name}" TO {RUNTIME_ROLE}, {MAINTENANCE_ROLE}'
            )
        )
        _enable_rls(table_name)

    op.execute(
        sa.text(
            f"GRANT USAGE, SELECT ON SEQUENCE compliance_audit_events_id_seq TO {RUNTIME_ROLE}, {MAINTENANCE_ROLE}"
        )
    )
    op.execute(
        sa.text(
            f"REVOKE UPDATE, DELETE ON TABLE authorization_audit_events FROM {RUNTIME_ROLE}, {MAINTENANCE_ROLE}"
        )
    )
    op.execute(
        sa.text(
            f"REVOKE UPDATE, DELETE ON TABLE compliance_audit_events FROM {RUNTIME_ROLE}, {MAINTENANCE_ROLE}"
        )
    )
    op.execute(
        sa.text(
            "CREATE FUNCTION reject_immutable_audit_mutation() RETURNS trigger "
            "LANGUAGE plpgsql AS $$ BEGIN "
            "RAISE EXCEPTION 'immutable audit events cannot be mutated' USING ERRCODE = '42501'; "
            "END; $$"
        )
    )
    for table_name in IMMUTABLE_AUDIT_TABLES:
        op.execute(
            sa.text(
                f"CREATE TRIGGER trg_{table_name}_immutable BEFORE UPDATE OR DELETE "
                f'ON "{table_name}" FOR EACH ROW EXECUTE FUNCTION reject_immutable_audit_mutation()'
            )
        )


def downgrade() -> None:
    """Remove T11 structures while leaving earlier audit data schema intact."""
    for table_name in IMMUTABLE_AUDIT_TABLES:
        op.execute(sa.text(f'DROP TRIGGER IF EXISTS trg_{table_name}_immutable ON "{table_name}"'))
    op.execute(sa.text("DROP FUNCTION IF EXISTS reject_immutable_audit_mutation()"))
    op.execute(
        sa.text(
            f"GRANT UPDATE, DELETE ON TABLE authorization_audit_events TO {RUNTIME_ROLE}, {MAINTENANCE_ROLE}"
        )
    )
    for table_name in reversed(T11_TENANT_OWNED_TABLES):
        op.drop_table(table_name)
