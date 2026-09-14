"""Canonical data classification and lifecycle policy registry."""

from dataclasses import dataclass
from enum import StrEnum


class DataOwner(StrEnum):
    """Ownership boundary for a production dataset."""

    TENANT_OWNED = "TENANT_OWNED"
    GLOBAL_SYSTEM = "GLOBAL_SYSTEM"


class DataClassification(StrEnum):
    """Small handling-oriented data classification vocabulary."""

    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED = "RESTRICTED"


class DeletionStrategy(StrEnum):
    """Supported lifecycle action for an eligible record."""

    HARD_DELETE = "HARD_DELETE"
    TOMBSTONE = "TOMBSTONE"
    DELETE_EXTERNAL_OBJECT = "DELETE_EXTERNAL_OBJECT"
    RETAIN = "RETAIN"


class ExportPolicy(StrEnum):
    """Approval handling required before data export."""

    NOT_EXPORTABLE = "NOT_EXPORTABLE"
    AUTHORIZED = "AUTHORIZED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"


@dataclass(frozen=True, slots=True)
class DatasetPolicy:
    """Classification, retention, export, and audit handling for one dataset."""

    dataset: str
    owner: DataOwner
    tenant_key: str | None
    contains_sensitive_data: bool
    classification: DataClassification
    retention_category: str
    retention_days: int | None
    deletion_strategy: DeletionStrategy
    export_policy: ExportPolicy
    audit_required: bool
    retention_enabled: bool = False
    eligibility_field: str | None = None
    batch_limit: int = 100


def _tenant(
    dataset: str,
    classification: DataClassification,
    category: str,
    *,
    sensitive: bool = False,
    retention_days: int | None = None,
    strategy: DeletionStrategy = DeletionStrategy.RETAIN,
    export: ExportPolicy = ExportPolicy.NOT_EXPORTABLE,
    audit: bool = False,
    enabled: bool = False,
    timestamp: str | None = None,
) -> DatasetPolicy:
    return DatasetPolicy(
        dataset=dataset,
        owner=DataOwner.TENANT_OWNED,
        tenant_key="tenant_id",
        contains_sensitive_data=sensitive,
        classification=classification,
        retention_category=category,
        retention_days=retention_days,
        deletion_strategy=strategy,
        export_policy=export,
        audit_required=audit,
        retention_enabled=enabled,
        eligibility_field=timestamp,
    )


_TENANT_DATASETS = (
    _tenant("users", DataClassification.RESTRICTED, "identity", sensitive=True, audit=True),
    _tenant(
        "external_identities", DataClassification.RESTRICTED, "identity", sensitive=True, audit=True
    ),
    _tenant(
        "authorization_audit_events", DataClassification.RESTRICTED, "audit_indefinite", audit=True
    ),
    _tenant(
        "compliance_audit_events", DataClassification.RESTRICTED, "audit_indefinite", audit=True
    ),
    _tenant(
        "approval_requests",
        DataClassification.RESTRICTED,
        "approval_evidence",
        sensitive=True,
        audit=True,
    ),
    _tenant(
        "sensitive_export_artifacts",
        DataClassification.RESTRICTED,
        "ephemeral_export",
        sensitive=True,
        retention_days=1,
        strategy=DeletionStrategy.HARD_DELETE,
        audit=True,
        enabled=True,
        timestamp="expires_at",
    ),
    _tenant(
        "orders",
        DataClassification.CONFIDENTIAL,
        "business_record",
        sensitive=True,
        export=ExportPolicy.APPROVAL_REQUIRED,
        audit=True,
    ),
    _tenant(
        "refund_applications",
        DataClassification.CONFIDENTIAL,
        "business_record",
        sensitive=True,
        export=ExportPolicy.APPROVAL_REQUIRED,
        audit=True,
    ),
    _tenant(
        "complaint_tickets",
        DataClassification.CONFIDENTIAL,
        "customer_service",
        sensitive=True,
        audit=True,
    ),
    _tenant(
        "message_cards",
        DataClassification.CONFIDENTIAL,
        "conversation",
        sensitive=True,
        retention_days=365,
        strategy=DeletionStrategy.HARD_DELETE,
        export=ExportPolicy.APPROVAL_REQUIRED,
        enabled=True,
        timestamp="created_at",
    ),
    _tenant(
        "conversations",
        DataClassification.CONFIDENTIAL,
        "conversation_runtime",
        sensitive=True,
        retention_days=365,
        strategy=DeletionStrategy.HARD_DELETE,
        export=ExportPolicy.APPROVAL_REQUIRED,
        timestamp="created_at",
    ),
    _tenant(
        "conversation_turns",
        DataClassification.CONFIDENTIAL,
        "conversation_runtime",
        sensitive=True,
        retention_days=365,
        strategy=DeletionStrategy.HARD_DELETE,
        export=ExportPolicy.APPROVAL_REQUIRED,
        timestamp="created_at",
    ),
    _tenant(
        "conversation_runs",
        DataClassification.CONFIDENTIAL,
        "conversation_runtime",
        sensitive=True,
        retention_days=180,
        strategy=DeletionStrategy.HARD_DELETE,
        export=ExportPolicy.APPROVAL_REQUIRED,
        audit=True,
        timestamp="created_at",
    ),
    _tenant(
        "conversation_runtime_events",
        DataClassification.CONFIDENTIAL,
        "runtime_event",
        sensitive=True,
        retention_days=90,
        strategy=DeletionStrategy.HARD_DELETE,
        audit=True,
        timestamp="created_at",
    ),
    _tenant(
        "conversation_tool_executions",
        DataClassification.CONFIDENTIAL,
        "runtime_tool_metadata",
        sensitive=True,
        retention_days=90,
        strategy=DeletionStrategy.HARD_DELETE,
        audit=True,
        timestamp="created_at",
    ),
    _tenant(
        "knowledge_documents",
        DataClassification.CONFIDENTIAL,
        "knowledge_upload",
        sensitive=True,
        retention_days=365,
        strategy=DeletionStrategy.DELETE_EXTERNAL_OBJECT,
        export=ExportPolicy.APPROVAL_REQUIRED,
        audit=True,
        enabled=True,
        timestamp="created_at",
    ),
    _tenant(
        "user_profiles",
        DataClassification.RESTRICTED,
        "memory",
        sensitive=True,
        retention_days=90,
        strategy=DeletionStrategy.HARD_DELETE,
        export=ExportPolicy.APPROVAL_REQUIRED,
        audit=True,
        timestamp="updated_at",
    ),
    _tenant(
        "user_preferences",
        DataClassification.CONFIDENTIAL,
        "memory",
        sensitive=True,
        retention_days=90,
        strategy=DeletionStrategy.HARD_DELETE,
        export=ExportPolicy.APPROVAL_REQUIRED,
        timestamp="updated_at",
    ),
    _tenant(
        "interaction_summaries",
        DataClassification.CONFIDENTIAL,
        "memory",
        sensitive=True,
        retention_days=90,
        strategy=DeletionStrategy.TOMBSTONE,
        export=ExportPolicy.APPROVAL_REQUIRED,
        audit=True,
        timestamp="updated_at",
    ),
    _tenant(
        "user_facts",
        DataClassification.CONFIDENTIAL,
        "memory",
        sensitive=True,
        retention_days=90,
        strategy=DeletionStrategy.HARD_DELETE,
        export=ExportPolicy.APPROVAL_REQUIRED,
        timestamp="updated_at",
    ),
    _tenant("agent_configs", DataClassification.INTERNAL, "configuration"),
    _tenant("routing_rules", DataClassification.INTERNAL, "configuration"),
    _tenant(
        "agent_config_versions", DataClassification.INTERNAL, "configuration_history", audit=True
    ),
    _tenant(
        "agent_config_audit_logs", DataClassification.CONFIDENTIAL, "audit_indefinite", audit=True
    ),
    _tenant("experiments", DataClassification.INTERNAL, "evaluation"),
    _tenant("experiment_variants", DataClassification.INTERNAL, "evaluation"),
    _tenant(
        "experiment_assignments", DataClassification.CONFIDENTIAL, "evaluation", sensitive=True
    ),
    _tenant("experiment_metrics", DataClassification.INTERNAL, "evaluation"),
    _tenant(
        "confidence_audits",
        DataClassification.CONFIDENTIAL,
        "ai_execution",
        sensitive=True,
        audit=True,
    ),
    _tenant(
        "message_feedbacks",
        DataClassification.CONFIDENTIAL,
        "feedback",
        sensitive=True,
        retention_days=365,
        strategy=DeletionStrategy.HARD_DELETE,
        export=ExportPolicy.APPROVAL_REQUIRED,
        audit=True,
        enabled=True,
        timestamp="created_at",
    ),
    _tenant("quality_scores", DataClassification.INTERNAL, "evaluation"),
    _tenant("shadow_test_results", DataClassification.CONFIDENTIAL, "ai_execution", sensitive=True),
    _tenant("adversarial_test_runs", DataClassification.INTERNAL, "evaluation"),
    _tenant(
        "graph_execution_logs", DataClassification.CONFIDENTIAL, "operational_log", sensitive=True
    ),
    _tenant("graph_node_logs", DataClassification.INTERNAL, "operational_log"),
    _tenant(
        "supervisor_decisions",
        DataClassification.CONFIDENTIAL,
        "ai_execution",
        sensitive=True,
        audit=True,
    ),
    _tenant(
        "multi_intent_decision_logs",
        DataClassification.CONFIDENTIAL,
        "ai_execution",
        sensitive=True,
    ),
    _tenant("prompt_effect_reports", DataClassification.INTERNAL, "evaluation"),
    _tenant(
        "audit_logs", DataClassification.CONFIDENTIAL, "business_review", sensitive=True, audit=True
    ),
    _tenant(
        "pii_audit_logs",
        DataClassification.RESTRICTED,
        "audit_indefinite",
        sensitive=True,
        audit=True,
    ),
    _tenant(
        "review_tickets",
        DataClassification.CONFIDENTIAL,
        "human_review",
        sensitive=True,
        audit=True,
    ),
    _tenant("reviewer_metrics", DataClassification.INTERNAL, "operational_metric"),
    _tenant("token_usage_logs", DataClassification.CONFIDENTIAL, "operational_log", sensitive=True),
    _tenant("optimization_suggestions", DataClassification.INTERNAL, "evaluation"),
    _tenant("alert_rules", DataClassification.INTERNAL, "operations"),
    _tenant(
        "alert_events", DataClassification.CONFIDENTIAL, "operations", sensitive=True, audit=True
    ),
    _tenant(
        "alert_notifications",
        DataClassification.CONFIDENTIAL,
        "operations",
        sensitive=True,
        audit=True,
    ),
    _tenant(
        "outbox_events",
        DataClassification.CONFIDENTIAL,
        "task_metadata",
        sensitive=True,
        audit=True,
    ),
    _tenant("task_execution_receipts", DataClassification.INTERNAL, "task_metadata", audit=True),
)

_GLOBAL_DATASETS = (
    DatasetPolicy(
        "tenants",
        DataOwner.GLOBAL_SYSTEM,
        None,
        False,
        DataClassification.INTERNAL,
        "identity_registry",
        None,
        DeletionStrategy.RETAIN,
        ExportPolicy.NOT_EXPORTABLE,
        True,
    ),
    DatasetPolicy(
        "alembic_version",
        DataOwner.GLOBAL_SYSTEM,
        None,
        False,
        DataClassification.INTERNAL,
        "system_metadata",
        None,
        DeletionStrategy.RETAIN,
        ExportPolicy.NOT_EXPORTABLE,
        False,
    ),
    DatasetPolicy(
        "qdrant_knowledge_points",
        DataOwner.TENANT_OWNED,
        "tenant_id",
        True,
        DataClassification.CONFIDENTIAL,
        "derived_knowledge",
        365,
        DeletionStrategy.HARD_DELETE,
        ExportPolicy.NOT_EXPORTABLE,
        False,
    ),
    DatasetPolicy(
        "qdrant_memory_points",
        DataOwner.TENANT_OWNED,
        "tenant_id",
        True,
        DataClassification.CONFIDENTIAL,
        "derived_memory",
        90,
        DeletionStrategy.HARD_DELETE,
        ExportPolicy.NOT_EXPORTABLE,
        False,
    ),
    DatasetPolicy(
        "redis_tenant_runtime",
        DataOwner.TENANT_OWNED,
        "tenant namespace",
        False,
        DataClassification.INTERNAL,
        "ephemeral_runtime",
        None,
        DeletionStrategy.HARD_DELETE,
        ExportPolicy.NOT_EXPORTABLE,
        False,
    ),
    DatasetPolicy(
        "local_knowledge_objects",
        DataOwner.TENANT_OWNED,
        "tenant path segment",
        True,
        DataClassification.CONFIDENTIAL,
        "knowledge_upload",
        365,
        DeletionStrategy.DELETE_EXTERNAL_OBJECT,
        ExportPolicy.APPROVAL_REQUIRED,
        True,
    ),
    DatasetPolicy(
        "bundled_seed_data",
        DataOwner.GLOBAL_SYSTEM,
        None,
        False,
        DataClassification.PUBLIC,
        "source_control",
        None,
        DeletionStrategy.RETAIN,
        ExportPolicy.AUTHORIZED,
        False,
    ),
)

DATASET_POLICIES: dict[str, DatasetPolicy] = {
    policy.dataset: policy for policy in (*_TENANT_DATASETS, *_GLOBAL_DATASETS)
}


def assert_classification_registry_complete(production_tables: set[str]) -> None:
    """Fail when a production table lacks a lifecycle policy or a policy is malformed."""
    missing = production_tables - DATASET_POLICIES.keys()
    if missing:
        raise RuntimeError(f"Unclassified production datasets: {', '.join(sorted(missing))}")
    invalid = [
        policy.dataset
        for policy in DATASET_POLICIES.values()
        if policy.owner is DataOwner.TENANT_OWNED and not policy.tenant_key
    ]
    if invalid:
        raise RuntimeError(
            f"Tenant-owned datasets without tenant key: {', '.join(sorted(invalid))}"
        )
