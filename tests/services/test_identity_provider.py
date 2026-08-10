"""Enterprise identity-provider adapter tests."""

import httpx
import pytest

from app.services.identity_provider import IdentityProviderError, OIDCUserInfoProvider


@pytest.mark.asyncio
async def test_oidc_userinfo_provider_normalizes_valid_identity() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"sub": "employee-7", "email": "agent@example.com", "name": "Agent Liu"},
        )
    )
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OIDCUserInfoProvider("https://idp.example.com/userinfo", client)
        identity = await provider.authenticate("enterprise-access-token")

    assert identity.subject == "employee-7"
    assert str(identity.email) == "agent@example.com"
    assert identity.display_name == "Agent Liu"


@pytest.mark.asyncio
async def test_oidc_userinfo_provider_rejects_invalid_upstream_token() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(401))
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OIDCUserInfoProvider("https://idp.example.com/userinfo", client)
        with pytest.raises(IdentityProviderError):
            await provider.authenticate("invalid-enterprise-token")
