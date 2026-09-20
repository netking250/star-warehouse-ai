"""Tests for the focused P-UAT-03 fixture and browser-session preflight."""

import pytest

from scripts.uat03_final_fix import (
    TRANSACTION_CASE_IDS,
    BenchmarkIdentity,
    OrderOwnership,
    UATPreflightError,
    assert_transaction_ownership,
    browser_login_payload,
    identity_for_case,
)


def test_all_transaction_cases_use_one_benchmark_identity() -> None:
    identity = BenchmarkIdentity(tenant_id="tenant-a", user_id=2)

    assert {identity_for_case(case_id, identity) for case_id in TRANSACTION_CASE_IDS} == {identity}


def test_transaction_preflight_accepts_one_tenant_user_owner() -> None:
    identity = BenchmarkIdentity(tenant_id="tenant-a", user_id=2)
    orders = [
        OrderOwnership(order_sn=order_sn, tenant_id="tenant-a", user_id=2)
        for order_sn in ("SN649201", "SN649202", "SN649203")
    ]

    assert_transaction_ownership(identity, orders)


def test_transaction_preflight_stops_on_owner_mismatch() -> None:
    identity = BenchmarkIdentity(tenant_id="tenant-a", user_id=1)
    orders = [
        OrderOwnership(order_sn=order_sn, tenant_id="tenant-a", user_id=2)
        for order_sn in ("SN649201", "SN649202", "SN649203")
    ]

    with pytest.raises(UATPreflightError, match="ownership preflight failed"):
        assert_transaction_ownership(identity, orders)


def test_browser_login_payload_uses_supported_tenant_aware_contract() -> None:
    payload = browser_login_payload(
        username="uat-customer", password="not-a-real-secret", tenant_id="tenant-a"
    )

    assert payload == {
        "username": "uat-customer",
        "password": "not-a-real-secret",
        "tenant_id": "tenant-a",
    }
