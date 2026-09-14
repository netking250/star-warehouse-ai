"""Regression tests for the Alembic revision graph."""

import re
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VERSIONS_DIR = REPOSITORY_ROOT / "migrations" / "versions"
CURRENT_HEAD = "e9f0a1b2c3d4"


def test_alembic_revision_graph_has_exactly_one_head() -> None:
    """Keep deploys deterministic by requiring one Alembic head."""
    config = Config(REPOSITORY_ROOT / "alembic.ini")
    script = ScriptDirectory.from_config(config)

    heads = script.get_heads()

    assert len(heads) == 1, f"Expected exactly one Alembic head, found: {heads}"


def test_feedback_enrichment_runs_after_message_feedbacks_creation() -> None:
    """Require the feedback enrichment revision to follow the table creator."""
    config = Config(REPOSITORY_ROOT / "alembic.ini")
    script = ScriptDirectory.from_config(config)

    enrichment = script.get_revision("3a9f8e7b2c1d")

    assert enrichment.down_revision == "053eaa2f0a66"


def test_phase3_revision_does_not_repeat_feedback_enrichment_ddl() -> None:
    """Keep earlier schema objects owned by their dedicated revisions."""
    phase3_source = (VERSIONS_DIR / "c61a28a53622_add_phase3_review_queue_and_token_.py").read_text(
        encoding="utf-8"
    )

    duplicate_operation = re.compile(
        r"op\.(?:add|drop)_column\([\"']message_feedbacks[\"']"
        r"|op\.(?:create|drop)_table\([\"']experiment_metrics[\"']"
    )

    assert duplicate_operation.search(phase3_source) is None


def test_transactional_outbox_is_an_incremental_single_head_revision() -> None:
    """Keep T03 additive and downstream of the accepted tenant baseline."""
    config = Config(REPOSITORY_ROOT / "alembic.ini")
    script = ScriptDirectory.from_config(config)

    outbox_revision = script.get_revision("c8d7e6f5a4b3")

    assert outbox_revision.down_revision == "b7c6d5e4f3a2"
    assert script.get_heads() == [CURRENT_HEAD]


def test_task_receipts_are_an_incremental_single_head_revision() -> None:
    """Keep T04 receipt storage additive and downstream of T03."""
    config = Config(REPOSITORY_ROOT / "alembic.ini")
    script = ScriptDirectory.from_config(config)

    receipt_revision = script.get_revision("d9e8f7a6b5c4")

    assert receipt_revision.down_revision == "c8d7e6f5a4b3"
    assert script.get_heads() == [CURRENT_HEAD]


def test_tenant_domain_is_incremental_and_removes_implicit_defaults() -> None:
    """Keep T06 additive while making tenant ownership explicit."""
    config = Config(REPOSITORY_ROOT / "alembic.ini")
    script = ScriptDirectory.from_config(config)
    source = (VERSIONS_DIR / "f4a5b6c7d8e9_add_tenant_domain.py").read_text(encoding="utf-8")

    tenant_revision = script.get_revision("f4a5b6c7d8e9")

    assert tenant_revision.down_revision == "e3f4a5b6c7d8"
    assert 'op.create_table(\n        "tenants"' in source
    assert "ON CONFLICT (id) DO NOTHING" in source
    assert 'op.alter_column(table_name, "tenant_id", server_default=None' in source
    assert script.get_heads() == [CURRENT_HEAD]


def test_postgresql_rls_is_additive_after_tenant_domain() -> None:
    """Keep T07 policy installation downstream of the accepted T06 schema."""
    config = Config(REPOSITORY_ROOT / "alembic.ini")
    script = ScriptDirectory.from_config(config)

    rls_revision = script.get_revision("a5b6c7d8e9f0")

    assert rls_revision.down_revision == "f4a5b6c7d8e9"
    assert script.get_heads() == [CURRENT_HEAD]


def test_external_identity_binding_is_additive_after_postgresql_rls() -> None:
    """Keep T08 identity storage additive and protected by the accepted RLS boundary."""
    config = Config(REPOSITORY_ROOT / "alembic.ini")
    script = ScriptDirectory.from_config(config)
    source = (VERSIONS_DIR / "b6c7d8e9f0a1_add_external_identity_bindings.py").read_text(
        encoding="utf-8"
    )

    identity_revision = script.get_revision("b6c7d8e9f0a1")

    assert identity_revision.down_revision == "a5b6c7d8e9f0"
    assert "uq_external_identities_issuer_subject" in source
    assert "ENABLE ROW LEVEL SECURITY" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert script.get_heads() == [CURRENT_HEAD]


def test_authorization_audit_is_additive_after_enterprise_identity() -> None:
    """Keep T09 audit evidence additive and protected by forced tenant RLS."""
    config = Config(REPOSITORY_ROOT / "alembic.ini")
    script = ScriptDirectory.from_config(config)
    source = (VERSIONS_DIR / "c7d8e9f0a1b2_add_authorization_audit_events.py").read_text(
        encoding="utf-8"
    )

    authorization_revision = script.get_revision("c7d8e9f0a1b2")

    assert authorization_revision.down_revision == "b6c7d8e9f0a1"
    assert "authorization_audit_events" in source
    assert "ENABLE ROW LEVEL SECURITY" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert script.get_heads() == [CURRENT_HEAD]


def test_compliance_lifecycle_is_additive_and_protected() -> None:
    """Keep T11 additive, single-headed, and explicit about audit/RLS controls."""
    config = Config(REPOSITORY_ROOT / "alembic.ini")
    script = ScriptDirectory.from_config(config)
    source = (VERSIONS_DIR / "d8e9f0a1b2c3_add_compliance_lifecycle.py").read_text(encoding="utf-8")

    compliance_revision = script.get_revision("d8e9f0a1b2c3")

    assert compliance_revision.down_revision == "c7d8e9f0a1b2"
    assert "compliance_audit_events" in source
    assert "approval_requests" in source
    assert "sensitive_export_artifacts" in source
    assert "ENABLE ROW LEVEL SECURITY" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "REVOKE UPDATE, DELETE ON TABLE compliance_audit_events" in source
    assert script.get_heads() == [CURRENT_HEAD]


def test_durable_conversation_runtime_is_additive_and_protected() -> None:
    """Keep T12 downstream of T11 with immediate forced tenant RLS."""
    config = Config(REPOSITORY_ROOT / "alembic.ini")
    script = ScriptDirectory.from_config(config)
    source = (VERSIONS_DIR / "e9f0a1b2c3d4_add_durable_conversation_runtime.py").read_text(
        encoding="utf-8"
    )

    runtime_revision = script.get_revision(CURRENT_HEAD)

    assert runtime_revision.down_revision == "d8e9f0a1b2c3"
    assert "conversation_runs" in source
    assert "conversation_runtime_events" in source
    assert "conversation_tool_executions" in source
    assert "ENABLE ROW LEVEL SECURITY" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "WITH CHECK" in source
    assert script.get_heads() == [CURRENT_HEAD]
