"""Tenant isolation tests for database and storage namespaces."""

import uuid

import pytest
from sqlmodel import SQLModel, select

import app.models  # noqa: F401
from app.core.tenancy import (
    TenantIsolationError,
    get_current_tenant_id,
    namespaced_collection,
    namespaced_key,
    tenant_scope,
)
from app.models.tenant import TenantScopedModel
from app.models.user import User


def _user(username: str, email: str) -> User:
    return User(
        username=username,
        password_hash="test-password-hash",
        email=email,
        full_name="Tenant Test",
        is_active=True,
    )


def test_all_platform_tables_are_tenant_scoped() -> None:
    unscoped = [
        table.name
        for table in SQLModel.metadata.tables.values()
        if table.name != "alembic_version" and "tenant_id" not in table.c
    ]

    assert unscoped == []


def test_storage_namespaces_include_environment_and_tenant() -> None:
    with tenant_scope("tenant-blue"):
        assert get_current_tenant_id() == "tenant-blue"
        assert namespaced_key("cart:42").endswith(":tenant-blue:cart:42")
        assert namespaced_collection("knowledge.chunks").endswith("_knowledge_chunks")

    assert get_current_tenant_id() == "default"


@pytest.mark.asyncio
async def test_database_selects_are_automatically_tenant_filtered(db_session) -> None:
    unique = uuid.uuid4().hex
    with tenant_scope("tenant-blue"):
        blue = _user(f"shared-{unique}", f"shared-{unique}@example.com")
        db_session.add(blue)
        await db_session.flush()

    with tenant_scope("tenant-green"):
        green = _user(f"shared-{unique}", f"shared-{unique}@example.com")
        db_session.add(green)
        await db_session.flush()

    with tenant_scope("tenant-blue"):
        result = await db_session.exec(select(User).where(User.username == f"shared-{unique}"))
        users = result.all()
        assert [user.tenant_id for user in users] == ["tenant-blue"]

    with tenant_scope("tenant-green"):
        result = await db_session.exec(select(User).where(User.username == f"shared-{unique}"))
        users = result.all()
        assert [user.tenant_id for user in users] == ["tenant-green"]


@pytest.mark.asyncio
async def test_database_rejects_cross_tenant_writes(db_session) -> None:
    with tenant_scope("tenant-blue"):
        record = _user(f"foreign-{uuid.uuid4().hex}", f"foreign-{uuid.uuid4().hex}@example.com")
        record.tenant_id = "tenant-green"
        db_session.add(record)

        with pytest.raises(TenantIsolationError):
            await db_session.flush()


def test_tenant_scoped_models_share_the_enforcement_marker() -> None:
    assert isinstance(_user("marker-user", "marker@example.com"), TenantScopedModel)
