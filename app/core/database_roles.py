"""Provision least-privilege PostgreSQL login roles from configured secrets."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.core.rls import MAINTENANCE_CAPABILITY_ROLE, RUNTIME_CAPABILITY_ROLE

logger = logging.getLogger(__name__)
_ROLE_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_-]{0,62}$")


@dataclass(frozen=True, slots=True)
class DatabaseLogin:
    """Credentials and capability membership for one PostgreSQL login role."""

    username: str
    password: str
    capability_role: str


def _validate_login(login: DatabaseLogin) -> None:
    if not _ROLE_PATTERN.fullmatch(login.username):
        raise ValueError("PostgreSQL login role contains unsupported characters")
    if login.username == login.capability_role:
        raise ValueError("Login role must be distinct from the non-login capability role")
    if not login.password:
        raise ValueError(f"Password is required for PostgreSQL login role {login.username!r}")


async def provision_database_logins(
    *,
    admin_database_url: str,
    runtime_login: DatabaseLogin,
    maintenance_login: DatabaseLogin,
) -> None:
    """Create or harden configured login roles and grant fixed capabilities.

    Args:
        admin_database_url: Administrative URL used only for role provisioning.
        runtime_login: Normal API and tenant-worker login.
        maintenance_login: Outbox and scheduled-maintenance login.
    """
    logins = (runtime_login, maintenance_login)
    for login in logins:
        _validate_login(login)

    engine = create_async_engine(admin_database_url, pool_pre_ping=True)
    try:
        async with engine.begin() as connection:
            for login in logins:
                existing_role = (
                    await connection.execute(
                        text(
                            "SELECT rolsuper, rolcreatedb, rolcreaterole, rolbypassrls "
                            "FROM pg_roles WHERE rolname = :role_name"
                        ),
                        {"role_name": login.username},
                    )
                ).one_or_none()
                if existing_role is not None and any(existing_role):
                    raise ValueError(
                        f"Refusing to repurpose privileged PostgreSQL role {login.username!r}"
                    )
                memberships = set(
                    (
                        await connection.execute(
                            text(
                                "SELECT parent.rolname FROM pg_auth_members AS membership "
                                "JOIN pg_roles AS member ON member.oid = membership.member "
                                "JOIN pg_roles AS parent ON parent.oid = membership.roleid "
                                "WHERE member.rolname = :role_name"
                            ),
                            {"role_name": login.username},
                        )
                    ).scalars()
                )
                unexpected_memberships = memberships - {login.capability_role}
                if unexpected_memberships:
                    raise ValueError(
                        f"Refusing PostgreSQL login {login.username!r} with unexpected role "
                        "memberships"
                    )
                exists = existing_role is not None
                statement = await connection.scalar(
                    text(
                        "SELECT format("
                        ":template, CAST(:role_name AS text), CAST(:password AS text))"
                    ),
                    {
                        "template": (
                            "ALTER ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                            "NOINHERIT NOBYPASSRLS PASSWORD %L"
                            if exists
                            else "CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                            "NOINHERIT NOBYPASSRLS PASSWORD %L"
                        ),
                        "role_name": login.username,
                        "password": login.password,
                    },
                )
                if not isinstance(statement, str):
                    raise RuntimeError("PostgreSQL did not produce login role DDL")
                await connection.exec_driver_sql(statement)

                grant_statement = await connection.scalar(
                    text(
                        "SELECT format('GRANT %I TO %I', CAST(:capability AS text), "
                        "CAST(:role_name AS text))"
                    ),
                    {"capability": login.capability_role, "role_name": login.username},
                )
                if not isinstance(grant_statement, str):
                    raise RuntimeError("PostgreSQL did not produce capability grant DDL")
                await connection.exec_driver_sql(grant_statement)
                logger.info(
                    "PostgreSQL login role provisioned",
                    extra={
                        "database_login": login.username,
                        "database_capability": login.capability_role,
                    },
                )
    finally:
        await engine.dispose()


async def provision_configured_database_logins() -> None:
    """Provision runtime roles using settings without logging credentials."""
    if settings.POSTGRES_RUNTIME_USER is None:
        raise ValueError("POSTGRES_RUNTIME_USER is required for database role provisioning")
    if settings.POSTGRES_RUNTIME_PASSWORD is None:
        raise ValueError("POSTGRES_RUNTIME_PASSWORD is required for database role provisioning")
    if settings.POSTGRES_MAINTENANCE_USER is None:
        raise ValueError("POSTGRES_MAINTENANCE_USER is required for database role provisioning")
    if settings.POSTGRES_MAINTENANCE_PASSWORD is None:
        raise ValueError("POSTGRES_MAINTENANCE_PASSWORD is required for database role provisioning")
    await provision_database_logins(
        admin_database_url=settings.MIGRATION_DATABASE_URL,
        runtime_login=DatabaseLogin(
            username=settings.POSTGRES_RUNTIME_USER,
            password=settings.POSTGRES_RUNTIME_PASSWORD.get_secret_value(),
            capability_role=RUNTIME_CAPABILITY_ROLE,
        ),
        maintenance_login=DatabaseLogin(
            username=settings.POSTGRES_MAINTENANCE_USER,
            password=settings.POSTGRES_MAINTENANCE_PASSWORD.get_secret_value(),
            capability_role=MAINTENANCE_CAPABILITY_ROLE,
        ),
    )


if __name__ == "__main__":
    asyncio.run(provision_configured_database_logins())
