"""Tenant isolation tests for database and storage namespaces."""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import update
from sqlmodel import SQLModel, col, select

import app.models  # noqa: F401
from app.core.tenancy import (
    TenantContextMissingError,
    TenantIsolationError,
    clear_current_tenant,
    get_current_tenant_id,
    namespaced_collection,
    namespaced_key,
    reset_current_tenant,
    tenant_scope,
    tenant_storage_path,
)
from app.models.order import Order
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


def test_missing_tenant_context_fails_closed() -> None:
    token = clear_current_tenant()
    try:
        with pytest.raises(TenantContextMissingError, match="No tenant context"):
            get_current_tenant_id()
    finally:
        reset_current_tenant(token)


def test_all_platform_tables_are_tenant_scoped() -> None:
    unscoped = [
        table.name
        for table in SQLModel.metadata.tables.values()
        if table.name not in {"alembic_version", "tenants"} and "tenant_id" not in table.c
    ]

    assert unscoped == []


def test_storage_namespaces_include_environment_and_tenant(tmp_path) -> None:
    with tenant_scope("tenant-blue"):
        assert get_current_tenant_id() == "tenant-blue"
        assert namespaced_key("cart:42").endswith(":tenant-blue:cart:42")
        assert namespaced_collection("knowledge.chunks").endswith("_knowledge_chunks")
        assert tenant_storage_path(tmp_path, "document.md") == (
            tmp_path / "tenant" / "tenant-blue" / "document.md"
        )

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


@pytest.mark.asyncio
async def test_bulk_update_cannot_modify_another_tenants_row(db_session) -> None:
    unique = uuid.uuid4().hex
    with tenant_scope("tenant-green"):
        foreign_user = _user(f"bulk-{unique}", f"bulk-{unique}@example.com")
        db_session.add(foreign_user)
        await db_session.flush()
        assert foreign_user.id is not None
        foreign_id = foreign_user.id

    with tenant_scope("tenant-blue"):
        result = await db_session.execute(
            update(User).where(col(User.id) == foreign_id).values(full_name="Cross-tenant update")
        )

    assert result.rowcount == 0


@pytest.mark.asyncio
async def test_instance_delete_cannot_remove_another_tenants_row(db_session) -> None:
    unique = uuid.uuid4().hex
    with tenant_scope("tenant-green"):
        foreign_user = _user(f"delete-{unique}", f"delete-{unique}@example.com")
        db_session.add(foreign_user)
        await db_session.flush()

    with tenant_scope("tenant-blue"):
        await db_session.delete(foreign_user)
        with pytest.raises(TenantIsolationError):
            await db_session.flush()


@pytest.mark.asyncio
async def test_cross_tenant_foreign_key_relationship_is_rejected(db_session) -> None:
    unique = uuid.uuid4().hex
    with tenant_scope("tenant-green"):
        foreign_user = _user(f"relation-{unique}", f"relation-{unique}@example.com")
        db_session.add(foreign_user)
        await db_session.flush()
        assert foreign_user.id is not None

    with tenant_scope("tenant-blue"):
        order = Order(
            order_sn=f"ORDER-{unique[:20]}",
            user_id=foreign_user.id,
            total_amount=Decimal("10"),
            items=[],
            shipping_address="Test address",
        )
        db_session.add(order)

        with pytest.raises(TenantIsolationError, match="relationship"):
            await db_session.flush()


def test_tenant_scoped_models_share_the_enforcement_marker() -> None:
    assert isinstance(_user("marker-user", "marker@example.com"), TenantScopedModel)
