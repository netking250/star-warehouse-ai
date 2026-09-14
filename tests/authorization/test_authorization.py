"""Targeted T09 tenant authorization and revocation verification."""

import uuid

import pytest
import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException
from sqlmodel import func, select

from app.api.v1.auth import get_oidc_provider_dependency
from app.authorization.policy import (
    AuthenticatedPrincipal,
    AuthorizationContext,
    AuthorizationPolicy,
    Role,
    Scope,
    authorize,
    scopes_for_roles,
)
from app.authorization.route_inventory import (
    HTTP_ROUTE_POLICIES,
    WEBSOCKET_ROUTE_POLICIES,
    RouteClassification,
    RoutePolicy,
    assert_routes_classified,
    inventory_routes,
)
from app.core.config import settings
from app.core.database import async_session_maker
from app.core.security import (
    create_access_token,
    get_admin_user_id_ws,
    get_current_user_id_ws,
)
from app.core.tenancy import TenantContext, TenantStatus, tenant_scope
from app.main import app
from app.models.authorization_audit import AuthorizationAuditAction, AuthorizationAuditEvent
from app.models.tenant import Tenant
from app.models.user import User
from app.services.authorization_service import AuthorizationService
from app.services.identity_provider import ExternalIdentity

_T11_HTTP_ROUTES = frozenset(
    {
        ("POST", "/api/v1/admin/feedback/export-requests"),
        ("GET", "/api/v1/admin/compliance/approvals"),
        ("POST", "/api/v1/admin/compliance/approvals/{approval_id}/decision"),
        ("POST", "/api/v1/admin/compliance/retention/{dataset}/dry-run"),
        ("POST", "/api/v1/admin/compliance/retention/{dataset}/execute"),
        # Existing feedback export is now a sensitive, approval-gated operation.
        ("GET", "/api/v1/admin/feedback/export"),
    }
)


class StubOIDCProvider:
    """Return a verified identity after the cryptographic provider boundary."""

    def __init__(self, email: str) -> None:
        self.email = email

    async def authenticate_callback(
        self, redis: aioredis.Redis, *, state: str, code: str
    ) -> tuple[ExternalIdentity, str]:
        return (
            ExternalIdentity(
                provider="enterprise-oidc",
                issuer="https://idp.example.com/t09",
                subject=f"t09-{self.email}",
                email=self.email,
                email_verified=True,
            ),
            settings.LOCAL_BOOTSTRAP_TENANT_ID,
        )


async def _create_user(
    *,
    role: Role = Role.CUSTOMER,
    active: bool = True,
    tenant_id: str | None = None,
    password: str = "t09-password",
) -> User:
    selected_tenant = tenant_id or settings.LOCAL_BOOTSTRAP_TENANT_ID
    unique = uuid.uuid4().hex[:12]
    with tenant_scope(selected_tenant):
        async with async_session_maker() as session, session.begin():
            user = User(
                tenant_id=selected_tenant,
                username=f"t09_{unique}",
                password_hash=User.hash_password(password),
                email=f"t09_{unique}@example.com",
                full_name="T09 Authorization User",
                role=role.value,
                is_admin=role is Role.SUPER_ADMIN,
                is_active=active,
            )
            session.add(user)
            await session.flush()
            assert user.id is not None
            return user


def _token(user: User, *, roles: list[Role] | None = None, scopes: list[str] | None = None) -> str:
    assert user.id is not None
    return create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        roles=roles or [Role.SUPER_ADMIN if user.is_admin else Role(user.role)],
        scopes=scopes,
    )


@pytest.mark.asyncio
async def test_protected_route_without_authentication_returns_401(client) -> None:
    response = await client.get("/api/v1/admin/authorization/memberships")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_authenticated_user_without_tenant_membership_returns_403(client) -> None:
    token = create_access_token(
        user_id=2_000_000_000,
        tenant_id=settings.LOCAL_BOOTSTRAP_TENANT_ID,
        roles=[Role.SUPER_ADMIN],
        scopes=["*"],
    )

    response = await client.get(
        "/api/v1/admin/authorization/memberships",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Access is not permitted"}


@pytest.mark.asyncio
async def test_member_without_required_scope_returns_403(client) -> None:
    user = await _create_user(role=Role.CUSTOMER)

    response = await client.get(
        "/api/v1/admin/authorization/memberships",
        headers={"Authorization": f"Bearer {_token(user)}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_current_tenant_member_with_scope_is_allowed(client) -> None:
    auditor = await _create_user(role=Role.AUDITOR)

    response = await client.get(
        "/api/v1/admin/authorization/memberships",
        headers={"Authorization": f"Bearer {_token(auditor)}"},
    )

    assert response.status_code == 200
    assert any(item["user_id"] == auditor.id for item in response.json())


@pytest.mark.asyncio
async def test_tenant_a_admin_without_tenant_b_membership_is_denied(client) -> None:
    tenant_b = f"t09-b-{uuid.uuid4().hex[:10]}"
    async with async_session_maker() as session, session.begin():
        session.add(
            Tenant(
                id=tenant_b,
                slug=tenant_b,
                display_name="T09 Tenant B",
                status=TenantStatus.ACTIVE,
            )
        )
    tenant_a_admin = await _create_user(role=Role.SUPER_ADMIN)
    assert tenant_a_admin.id is not None
    stale_tenant_a_authority = create_access_token(
        user_id=tenant_a_admin.id,
        tenant_id=tenant_b,
        roles=[Role.SUPER_ADMIN],
        scopes=["*"],
    )

    response = await client.get(
        "/api/v1/admin/authorization/memberships",
        headers={"Authorization": f"Bearer {stale_tenant_a_authority}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_removed_role_is_effective_with_same_valid_jwt(client) -> None:
    auditor = await _create_user(role=Role.AUDITOR)
    token = _token(auditor, roles=[Role.SUPER_ADMIN], scopes=["*"])
    headers = {"Authorization": f"Bearer {token}"}

    assert (
        await client.get("/api/v1/admin/authorization/memberships", headers=headers)
    ).status_code == 200
    with tenant_scope(auditor.tenant_id):
        async with async_session_maker() as session, session.begin():
            current = await session.get(User, auditor.id)
            assert current is not None
            current.role = Role.CUSTOMER.value
            current.is_admin = False
            session.add(current)

    response = await client.get("/api/v1/admin/authorization/memberships", headers=headers)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_revoked_membership_is_effective_with_same_valid_jwt(client) -> None:
    auditor = await _create_user(role=Role.AUDITOR)
    token = _token(auditor)
    headers = {"Authorization": f"Bearer {token}"}

    assert (
        await client.get("/api/v1/admin/authorization/memberships", headers=headers)
    ).status_code == 200
    with tenant_scope(auditor.tenant_id):
        async with async_session_maker() as session, session.begin():
            current = await session.get(User, auditor.id)
            assert current is not None
            current.is_active = False
            session.add(current)

    response = await client.get("/api/v1/admin/authorization/memberships", headers=headers)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_oidc_or_stale_token_roles_cannot_grant_local_authority(client) -> None:
    customer = await _create_user(role=Role.CUSTOMER)
    upstream_claims = ExternalIdentity.model_validate(
        {
            "provider": "enterprise-oidc",
            "issuer": "https://idp.example.com/t09",
            "subject": "untrusted-role-claim",
            "realm_access": {"roles": ["super_admin"]},
            "groups": ["administrators"],
        }
    )
    forged_snapshot = _token(customer, roles=[Role.SUPER_ADMIN], scopes=["*"])

    response = await client.get(
        "/api/v1/admin/authorization/memberships",
        headers={"Authorization": f"Bearer {forged_snapshot}"},
    )

    assert not hasattr(upstream_claims, "realm_access")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_sensitive_mutation_requires_stronger_scope_than_read(client) -> None:
    analyst = await _create_user(role=Role.ANALYST)
    headers = {"Authorization": f"Bearer {_token(analyst)}"}

    read_response = await client.get("/api/v1/admin/metrics/sessions", headers=headers)
    mutation_response = await client.post(
        "/api/v1/admin/shadow-test/run",
        params={"query": "safe test"},
        headers=headers,
    )

    assert read_response.status_code == 200
    assert mutation_response.status_code == 403


@pytest.mark.asyncio
async def test_ordinary_user_cannot_self_elevate(client) -> None:
    customer = await _create_user(role=Role.CUSTOMER)
    assert customer.id is not None

    response = await client.patch(
        f"/api/v1/admin/authorization/memberships/{customer.id}/role",
        json={"role": Role.SUPER_ADMIN.value},
        headers={"Authorization": f"Bearer {_token(customer)}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_identity_manager_cannot_change_self_or_grant_super_admin(client) -> None:
    manager = await _create_user(role=Role.IDENTITY_MANAGER)
    target = await _create_user(role=Role.CUSTOMER)
    assert manager.id is not None
    assert target.id is not None
    headers = {"Authorization": f"Bearer {_token(manager)}"}

    self_response = await client.patch(
        f"/api/v1/admin/authorization/memberships/{manager.id}/role",
        json={"role": Role.AUDITOR.value},
        headers=headers,
    )
    escalation_response = await client.patch(
        f"/api/v1/admin/authorization/memberships/{target.id}/role",
        json={"role": Role.SUPER_ADMIN.value},
        headers=headers,
    )

    assert self_response.status_code == 403
    assert escalation_response.status_code == 403


@pytest.mark.asyncio
async def test_identity_read_scope_cannot_mutate_authorization(client) -> None:
    auditor = await _create_user(role=Role.AUDITOR)
    target = await _create_user(role=Role.CUSTOMER)
    assert target.id is not None
    headers = {"Authorization": f"Bearer {_token(auditor)}"}

    assert (
        await client.get("/api/v1/admin/authorization/memberships", headers=headers)
    ).status_code == 200
    response = await client.patch(
        f"/api/v1/admin/authorization/memberships/{target.id}/role",
        json={"role": Role.AUDITOR.value},
        headers=headers,
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_last_active_tenant_administrator_cannot_be_removed(client) -> None:
    tenant_id = f"t09-last-admin-{uuid.uuid4().hex[:10]}"
    async with async_session_maker() as session, session.begin():
        session.add(
            Tenant(
                id=tenant_id,
                slug=tenant_id,
                display_name="T09 Last Admin Tenant",
                status=TenantStatus.ACTIVE,
            )
        )
    sole_admin = await _create_user(role=Role.SUPER_ADMIN, tenant_id=tenant_id)
    manager = await _create_user(role=Role.IDENTITY_MANAGER, tenant_id=tenant_id)
    assert sole_admin.id is not None

    response = await client.patch(
        f"/api/v1/admin/authorization/memberships/{sole_admin.id}/status",
        json={"active": False},
        headers={"Authorization": f"Bearer {_token(manager)}"},
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_role_mutation_commits_matching_audit_evidence(client) -> None:
    actor = await _create_user(role=Role.SUPER_ADMIN)
    target = await _create_user(role=Role.CUSTOMER)
    assert target.id is not None

    response = await client.patch(
        f"/api/v1/admin/authorization/memberships/{target.id}/role",
        json={"role": Role.AUDITOR.value},
        headers={"Authorization": f"Bearer {_token(actor)}"},
    )

    assert response.status_code == 200
    with tenant_scope(target.tenant_id):
        async with async_session_maker() as session:
            audit = (
                await session.exec(
                    select(AuthorizationAuditEvent).where(
                        AuthorizationAuditEvent.target_user_id == target.id
                    )
                )
            ).one()
            current = await session.get(User, target.id)
    assert current is not None
    assert current.role == Role.AUDITOR.value
    assert audit.action == AuthorizationAuditAction.ROLE_ASSIGNED
    assert audit.actor_user_id == actor.id
    assert audit.correlation_id


@pytest.mark.asyncio
async def test_role_and_audit_rollback_together() -> None:
    actor = await _create_user(role=Role.SUPER_ADMIN)
    target = await _create_user(role=Role.CUSTOMER)
    assert actor.id is not None
    assert target.id is not None
    tenant = TenantContext(
        tenant_id=target.tenant_id,
        slug=target.tenant_id,
        display_name="Default",
        status=TenantStatus.ACTIVE,
    )
    context = AuthorizationContext(
        principal=AuthenticatedPrincipal(
            tenant_id=target.tenant_id,
            user_id=actor.id,
            session_id="rollback-session",
            correlation_id="rollback-correlation",
            token_id="rollback-token",
        ),
        tenant=tenant,
        roles=frozenset({Role.SUPER_ADMIN}),
        scopes=frozenset({"*"}),
    )

    with tenant_scope(target.tenant_id):
        async with async_session_maker() as session:
            await AuthorizationService().assign_role(
                session,
                actor=context,
                target_user_id=target.id,
                new_role=Role.AUDITOR,
            )
            await session.rollback()
        async with async_session_maker() as verification:
            current = await verification.get(User, target.id)
            audit_count = (
                await verification.exec(
                    select(func.count())
                    .select_from(AuthorizationAuditEvent)
                    .where(AuthorizationAuditEvent.target_user_id == target.id)
                )
            ).one()

    assert current is not None
    assert current.role == Role.CUSTOMER.value
    assert audit_count == 0


def test_all_http_and_websocket_routes_are_explicitly_classified() -> None:
    entries, missing = inventory_routes(app)
    http_entries = [entry for entry in entries if entry.kind == "HTTP"]
    websocket_entries = [entry for entry in entries if entry.kind == "WEBSOCKET"]
    http_keys = {(entry.method, entry.path) for entry in http_entries}
    websocket_paths = {entry.path for entry in websocket_entries}

    assert missing == []
    assert len(websocket_entries) == 2
    # Every explicit policy must correspond to a registered route, while ``missing`` above
    # guarantees that every registered route has a policy and authorization dependency.
    assert set(HTTP_ROUTE_POLICIES) <= http_keys
    assert set(WEBSOCKET_ROUTE_POLICIES) <= websocket_paths
    assert http_keys >= _T11_HTTP_ROUTES
    assert all(
        HTTP_ROUTE_POLICIES[key].classification is RouteClassification.TENANT_SCOPE_REQUIRED
        for key in _T11_HTTP_ROUTES
    )
    assert (
        HTTP_ROUTE_POLICIES[("POST", "/api/v1/browser/login")].classification
        is RouteClassification.PUBLIC
    )
    assert (
        HTTP_ROUTE_POLICIES[("GET", "/api/v1/browser/csrf")].classification
        is RouteClassification.AUTHENTICATED
    )
    assert all(entry.policy.classification is not None for entry in entries)
    assert all(
        entry.policy.classification is RouteClassification.TENANT_SCOPE_REQUIRED
        for entry in websocket_entries
    )


def test_unclassified_business_route_fails_structural_guard() -> None:
    unclassified_app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @unclassified_app.get("/api/v1/forgotten")
    async def forgotten_route() -> dict[str, bool]:
        return {"ok": True}

    with pytest.raises(RuntimeError, match="Unclassified application routes"):
        assert_routes_classified(unclassified_app)


def test_classified_protected_route_without_dependency_fails_structural_guard() -> None:
    missing_guard_app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @missing_guard_app.get("/api/v1/missing-guard")
    async def missing_guard_route() -> dict[str, bool]:
        return {"ok": True}

    key = ("GET", "/api/v1/missing-guard")
    HTTP_ROUTE_POLICIES[key] = RoutePolicy(
        classification=RouteClassification.TENANT_SCOPE_REQUIRED,
        authorization=AuthorizationPolicy(scopes=frozenset({Scope.OPERATIONS_READ})),
    )
    try:
        with pytest.raises(RuntimeError, match="missing authorization dependency"):
            assert_routes_classified(missing_guard_app)
    finally:
        HTTP_ROUTE_POLICIES.pop(key)


@pytest.mark.asyncio
async def test_websocket_authentication_does_not_bypass_current_scope(redis_client) -> None:
    customer = await _create_user(role=Role.CUSTOMER)
    auditor = await _create_user(role=Role.AUDITOR)
    analyst = await _create_user(role=Role.ANALYST)

    assert await get_current_user_id_ws(_token(customer), redis_client) == customer.id
    with pytest.raises(HTTPException) as chat_denial:
        await get_current_user_id_ws(_token(auditor), redis_client)
    assert chat_denial.value.status_code == 403

    assert await get_admin_user_id_ws(_token(analyst), redis_client) == analyst.id
    with pytest.raises(HTTPException) as admin_denial:
        await get_admin_user_id_ws(_token(customer), redis_client)
    assert admin_denial.value.status_code == 403


@pytest.mark.asyncio
async def test_local_and_oidc_users_use_same_local_authorization_model(client, monkeypatch) -> None:
    local_user = await _create_user(role=Role.AUDITOR)
    oidc_user = await _create_user(role=Role.AUDITOR)
    monkeypatch.setattr(settings, "OIDC_ISSUER", "https://idp.example.com/t09")
    monkeypatch.setattr(settings, "OIDC_LINK_VERIFIED_EMAIL", True)
    monkeypatch.setattr(settings, "BROWSER_AUTH_COOKIE_SECURE", False)

    local_login = await client.post(
        "/api/v1/login",
        json={
            "username": local_user.username,
            "password": "t09-password",
            "tenant_id": local_user.tenant_id,
        },
    )
    assert local_login.status_code == 200
    local_protected = await client.get(
        "/api/v1/admin/authorization/memberships",
        headers={"Authorization": f"Bearer {local_login.json()['access_token']}"},
    )
    app.dependency_overrides[get_oidc_provider_dependency] = lambda: StubOIDCProvider(
        oidc_user.email
    )
    try:
        oidc_login = await client.get(
            "/api/v1/oidc/callback",
            params={"state": "t09-valid-state-value", "code": "t09-code"},
        )
    finally:
        app.dependency_overrides.pop(get_oidc_provider_dependency, None)

    assert oidc_login.status_code == 303
    oidc_protected = await client.get("/api/v1/admin/authorization/memberships")
    assert local_protected.status_code == 200
    assert oidc_protected.status_code == 200


def test_policy_uses_capabilities_and_super_admin_is_application_only() -> None:
    tenant = TenantContext(
        tenant_id="tenant-policy",
        slug="tenant-policy",
        display_name="Policy Tenant",
        status=TenantStatus.ACTIVE,
    )
    context = AuthorizationContext(
        principal=AuthenticatedPrincipal(
            tenant_id=tenant.tenant_id,
            user_id=7,
            session_id="policy-session",
            correlation_id="policy-correlation",
            token_id="policy-token",
        ),
        tenant=tenant,
        roles=frozenset({Role.ANALYST}),
        scopes=scopes_for_roles({Role.ANALYST}),
    )

    assert authorize(
        context, AuthorizationPolicy(scopes=frozenset({Scope.OPERATIONS_READ}))
    ).allowed
    assert not authorize(
        context, AuthorizationPolicy(scopes=frozenset({Scope.OPERATIONS_MANAGE}))
    ).allowed
    assert "BYPASSRLS" not in scopes_for_roles({Role.SUPER_ADMIN})
