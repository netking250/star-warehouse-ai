"""HTTP integration tests for current-state sensitive export authorization."""

import uuid

import pytest

from app.authorization.policy import Role
from app.core.database import async_session_maker
from app.core.security import create_access_token
from app.core.tenancy import tenant_scope
from app.models.user import User


async def _create_user(tenant_id: str, role: Role) -> User:
    unique = uuid.uuid4().hex[:10]
    with tenant_scope(tenant_id):
        async with async_session_maker() as session, session.begin():
            user = User(
                tenant_id=tenant_id,
                username=f"t11-{role.value}-{unique}",
                password_hash=User.hash_password("test-password"),
                email=f"t11-{unique}@example.com",
                full_name="T11 API User",
                role=role.value,
                is_admin=role is Role.SUPER_ADMIN,
            )
            session.add(user)
            await session.flush()
            assert user.id is not None
            return user


def _headers(user: User) -> dict[str, str]:
    assert user.id is not None
    token = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        roles=[Role(user.role)],
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_sensitive_export_rechecks_requester_role_after_approval(
    client, active_tenant: str
) -> None:
    requester = await _create_user(active_tenant, Role.ANALYST)
    approver = await _create_user(active_tenant, Role.AUDITOR)

    requested = await client.post(
        "/api/v1/admin/feedback/export-requests",
        json={"category": "delivery"},
        headers=_headers(requester),
    )
    assert requested.status_code == 200
    approval_id = requested.json()["id"]
    decided = await client.post(
        f"/api/v1/admin/compliance/approvals/{approval_id}/decision",
        json={"decision": "APPROVE"},
        headers=_headers(approver),
    )
    assert decided.status_code == 200

    with tenant_scope(active_tenant):
        async with async_session_maker() as session, session.begin():
            current = await session.get(User, requester.id)
            assert current is not None
            current.role = Role.CUSTOMER.value
            session.add(current)

    response = await client.get(
        "/api/v1/admin/feedback/export",
        params={"approval_id": approval_id, "category": "delivery"},
        headers=_headers(requester),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_sensitive_export_without_approval_is_denied(client, active_tenant: str) -> None:
    requester = await _create_user(active_tenant, Role.ANALYST)

    response = await client.get(
        "/api/v1/admin/feedback/export",
        params={"approval_id": str(uuid.uuid4())},
        headers=_headers(requester),
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_sensitive_export_self_approval_and_ordinary_approval_are_denied(
    client, active_tenant: str
) -> None:
    requester = await _create_user(active_tenant, Role.SUPER_ADMIN)
    ordinary = await _create_user(active_tenant, Role.CUSTOMER)
    requested = await client.post(
        "/api/v1/admin/feedback/export-requests",
        json={},
        headers=_headers(requester),
    )
    assert requested.status_code == 200
    approval_id = requested.json()["id"]

    unauthorized = await client.post(
        f"/api/v1/admin/compliance/approvals/{approval_id}/decision",
        json={"decision": "APPROVE"},
        headers=_headers(ordinary),
    )
    assert unauthorized.status_code == 403

    self_approval = await client.post(
        f"/api/v1/admin/compliance/approvals/{approval_id}/decision",
        json={"decision": "APPROVE"},
        headers=_headers(requester),
    )
    assert self_approval.status_code == 409
    assert "own sensitive export" in self_approval.json()["detail"]
