"""Enterprise identity-provider adapter boundary."""

from typing import Protocol

import httpx
from pydantic import BaseModel, EmailStr, ValidationError

from app.core.config import settings


class ExternalIdentity(BaseModel):
    """Normalized identity returned by an enterprise provider."""

    subject: str
    email: EmailStr
    display_name: str | None = None


class IdentityProviderError(RuntimeError):
    """Raised when an upstream identity cannot be safely validated."""


class IdentityProvider(Protocol):
    """Contract implemented by enterprise identity providers."""

    async def authenticate(self, access_token: str) -> ExternalIdentity:
        """Validate an upstream token and return a normalized identity."""
        ...


class OIDCUserInfoProvider:
    """OIDC adapter backed by the provider's UserInfo endpoint."""

    def __init__(self, userinfo_url: str, client: httpx.AsyncClient | None = None) -> None:
        if not userinfo_url.startswith("https://") and not settings.OIDC_ALLOW_INSECURE_HTTP:
            raise ValueError("OIDC userinfo URL must use HTTPS")
        self._userinfo_url = userinfo_url
        self._client = client

    async def authenticate(self, access_token: str) -> ExternalIdentity:
        client = self._client or httpx.AsyncClient(timeout=settings.OIDC_TIMEOUT_SECONDS)
        owns_client = self._client is None
        try:
            response = await client.get(
                self._userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            payload = response.json()
            return ExternalIdentity(
                subject=payload["sub"],
                email=payload["email"],
                display_name=payload.get("name"),
            )
        except (httpx.HTTPError, KeyError, ValueError, ValidationError) as error:
            raise IdentityProviderError("Enterprise identity validation failed") from error
        finally:
            if owns_client:
                await client.aclose()


def get_identity_provider() -> IdentityProvider:
    """Create the configured enterprise identity-provider adapter."""
    if not settings.OIDC_USERINFO_URL:
        raise IdentityProviderError("Enterprise identity provider is not configured")
    return OIDCUserInfoProvider(settings.OIDC_USERINFO_URL)
