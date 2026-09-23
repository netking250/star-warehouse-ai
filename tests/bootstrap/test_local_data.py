"""Behavior tests for the canonical local development data bootstrap."""

import pytest
from pydantic import SecretStr

from app.bootstrap.local_data import LocalBootstrapConfig, LocalBootstrapError


def _config(**overrides: object) -> LocalBootstrapConfig:
    values: dict[str, object] = {
        "enabled": True,
        "environment": "development",
        "tenant_id": "local-uat",
        "tenant_name": "Northstar Outfitters Local UAT",
        "customer_username": "northstar_customer",
        "customer_password": SecretStr("local-customer-change-me"),
        "customer_email": "customer@northstar.invalid",
        "admin_username": "northstar_operator",
        "admin_password": SecretStr("local-operator-change-me"),
        "admin_email": "operator@northstar.invalid",
    }
    values.update(overrides)
    return LocalBootstrapConfig(**values)


def test_local_bootstrap_refuses_production_even_when_enabled() -> None:
    """Production profiles must never create local bootstrap identities."""
    config = _config(environment="production")

    with pytest.raises(LocalBootstrapError, match="production"):
        config.validate_for_execution()


def test_local_bootstrap_requires_explicit_opt_in() -> None:
    """Normal application startup must not create accounts while disabled."""
    config = _config(enabled=False)

    with pytest.raises(LocalBootstrapError, match="LOCAL_BOOTSTRAP_ENABLED"):
        config.validate_for_execution()


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"tenant_name": ""}, "LOCAL_BOOTSTRAP_TENANT_NAME"),
        ({"customer_username": "same", "admin_username": "same"}, "distinct"),
        ({"customer_password": SecretStr("short")}, "at least 12"),
    ],
)
def test_local_bootstrap_rejects_incomplete_or_unsafe_identity_configuration(
    overrides: dict[str, object], message: str
) -> None:
    """Bootstrap identities require complete, distinct, nontrivial inputs."""
    config = _config(**overrides)

    with pytest.raises(LocalBootstrapError, match=message):
        config.validate_for_execution()
