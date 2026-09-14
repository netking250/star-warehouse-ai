"""Configuration guards for PostgreSQL runtime and migration role separation."""

from __future__ import annotations

import pytest
from pydantic import SecretStr
from sqlalchemy.engine import make_url

from app.core.config import Settings


def _database_settings(
    *,
    capability: str,
    database_name: str = "star_warehouse_ai",
    runtime_user: str | None = None,
    runtime_password: str | None = None,
    maintenance_user: str | None = None,
    maintenance_password: str | None = None,
) -> Settings:
    """Build only the settings fields exercised by database URL computation."""
    return Settings.model_construct(
        DB_CAPABILITY=capability,
        POSTGRES_SERVER="postgres.example.invalid",
        POSTGRES_PORT=5432,
        POSTGRES_DB=database_name,
        POSTGRES_USER="migration_admin",
        POSTGRES_PASSWORD=SecretStr("migration-secret"),
        POSTGRES_RUNTIME_USER=runtime_user,
        POSTGRES_RUNTIME_PASSWORD=(SecretStr(runtime_password) if runtime_password else None),
        POSTGRES_MAINTENANCE_USER=maintenance_user,
        POSTGRES_MAINTENANCE_PASSWORD=(
            SecretStr(maintenance_password) if maintenance_password else None
        ),
    )


@pytest.mark.parametrize("capability", ["runtime", "maintenance"])
def test_application_database_url_missing_dedicated_credentials_fails_closed(
    capability: str,
) -> None:
    """Never let a normal deployment fall back to the migration administrator."""
    configured = _database_settings(capability=capability)

    with pytest.raises(ValueError, match="Dedicated PostgreSQL credentials are required"):
        _ = configured.DATABASE_URL


def test_runtime_and_migration_database_urls_use_distinct_logins() -> None:
    """Keep the normal application login separate from the migration administrator."""
    configured = _database_settings(
        capability="runtime",
        runtime_user="application_runtime",
        runtime_password="runtime-secret",
    )

    assert make_url(configured.DATABASE_URL).username == "application_runtime"
    assert make_url(configured.MIGRATION_DATABASE_URL).username == "migration_admin"


def test_test_database_may_reuse_administrator_for_fixture_compatibility() -> None:
    """Allow destructive isolated test fixtures to retain their existing admin setup."""
    configured = _database_settings(capability="runtime", database_name="test_rls")

    assert make_url(configured.DATABASE_URL).username == "migration_admin"
