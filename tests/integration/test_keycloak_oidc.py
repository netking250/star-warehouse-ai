"""Optional real Keycloak discovery, JWKS, signature, and identity-resolution smoke."""

import os
import uuid

import httpx
import pytest

from app.core.config import settings
from app.core.database import async_session_maker
from app.models.user import User
from app.services.identity_provider import OIDCClient
from app.services.identity_service import IdentityService


@pytest.mark.keycloak
@pytest.mark.asyncio
async def test_real_keycloak_signed_identity_resolves_local_user(
    tenant_context: str, monkeypatch
) -> None:
    issuer = os.environ.get("T08_KEYCLOAK_ISSUER")
    if not issuer:
        pytest.skip("Set T08_KEYCLOAK_ISSUER to run the optional Keycloak profile smoke")
    client_secret = os.environ.get("T08_KEYCLOAK_CLIENT_SECRET", "dev-only-change-me-oidc-client")
    user_password = os.environ.get("T08_KEYCLOAK_USER_PASSWORD", "dev-only-change-me-user")
    client_id = "star-warehouse-ai"

    async with httpx.AsyncClient(timeout=10.0) as http_client:
        token_response = await http_client.post(
            f"{issuer}/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": client_id,
                "client_secret": client_secret,
                "username": "oidc-demo",
                "password": user_password,
                "scope": "openid profile email",
            },
        )
        token_response.raise_for_status()
        id_token = token_response.json()["id_token"]
        oidc = OIDCClient(
            issuer=issuer,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri="http://localhost:8000/api/v1/oidc/callback",
            allow_insecure_http=True,
            http_client=http_client,
        )
        discovery = await oidc.get_discovery()
        identity = await oidc.validate_id_token(id_token, expected_nonce=None)

    assert discovery.issuer == issuer
    assert identity.subject == "11111111-1111-4111-8111-111111111111"
    assert str(identity.email) == "keycloak-demo@example.com"
    assert identity.email_verified is True

    monkeypatch.setattr(settings, "OIDC_ISSUER", issuer)
    monkeypatch.setattr(settings, "OIDC_LINK_VERIFIED_EMAIL", True)
    unique = uuid.uuid4().hex[:10]
    async with async_session_maker() as session, session.begin():
        user = User(
            tenant_id=tenant_context,
            username=f"keycloak_{unique}",
            password_hash=User.hash_password("local-only-password"),
            email="keycloak-demo@example.com",
            full_name="Keycloak Demo",
            is_active=True,
        )
        session.add(user)

    async with async_session_maker() as session, session.begin():
        result = await IdentityService().authenticate_oidc(
            session,
            identity,
            tenant_id=tenant_context,
        )

    assert result.user.username == f"keycloak_{unique}"
    assert result.principal.subject == identity.subject
