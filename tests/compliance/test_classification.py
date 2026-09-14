"""Structural tests for the canonical production data inventory."""

from sqlmodel import SQLModel

import app.models  # noqa: F401
from app.compliance.classification import (
    DATASET_POLICIES,
    DataOwner,
    assert_classification_registry_complete,
)


def test_classification_registry_covers_every_production_table() -> None:
    production_tables = set(SQLModel.metadata.tables)

    assert_classification_registry_complete(production_tables)
    assert not production_tables - DATASET_POLICIES.keys()
    assert all(policy.retention_category for policy in DATASET_POLICIES.values())
    assert all(
        policy.tenant_key
        for policy in DATASET_POLICIES.values()
        if policy.owner is DataOwner.TENANT_OWNED
    )


def test_enabled_retention_policies_are_bounded_and_predicate_driven() -> None:
    enabled = [policy for policy in DATASET_POLICIES.values() if policy.retention_enabled]

    assert enabled
    assert all(policy.retention_days is not None for policy in enabled)
    assert all(policy.eligibility_field is not None for policy in enabled)
    assert all(1 <= policy.batch_limit <= 1000 for policy in enabled)
