"""Generic OpenID Connect provider adapter with discovery and JWKS validation."""

import asyncio
import base64
import hashlib
import json
import secrets
import time
from functools import lru_cache
from hmac import compare_digest
from typing import Protocol
from urllib.parse import urlencode, urlparse

import httpx
import jwt
import redis.asyncio as aioredis
from pydantic import BaseModel, ConfigDict, EmailStr, Field, StrictBool, ValidationError

from app.core.config import settings
from app.core.tenancy import namespaced_system_key, validate_tenant_id

SUPPORTED_ASYMMETRIC_ALGORITHMS = frozenset(
    {"RS256", "RS384", "RS512", "PS256", "PS384", "PS512", "ES256", "ES384", "ES512", "EdDSA"}
)


class ExternalIdentity(BaseModel):
    """Normalized, cryptographically verified identity from an OIDC provider."""

    provider: str
    issuer: str
    subject: str = Field(min_length=1, max_length=255)
    email: EmailStr | None = None
    email_verified: StrictBool = False
    display_name: str | None = None
    authentication_time: int | None = None


class OIDCLoginState(BaseModel):
    """Short-lived server-side authorization request state."""

    tenant_id: str
    nonce: str
    code_verifier: str


class OIDCDiscoveryDocument(BaseModel):
    """Discovery fields required by the authorization-code flow."""

    model_config = ConfigDict(extra="ignore")

    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str


class OIDCJWK(BaseModel):
    """JSON Web Key fields accepted by PyJWT."""

    model_config = ConfigDict(extra="allow")

    kid: str
    kty: str
    alg: str | None = None
    use: str | None = None
    n: str | None = None
    e: str | None = None
    x: str | None = None
    y: str | None = None
    crv: str | None = None


class OIDCJWKSet(BaseModel):
    """Validated JWKS response."""

    keys: list[OIDCJWK]


class OIDCTokenClaims(BaseModel):
    """Security-relevant claims from a verified ID token."""

    model_config = ConfigDict(extra="ignore")

    iss: str
    sub: str = Field(min_length=1, max_length=255)
    aud: str | list[str]
    exp: int
    iat: int
    nbf: int | None = None
    nonce: str | None = None
    email: EmailStr | None = None
    email_verified: StrictBool = False
    name: str | None = None
    auth_time: int | None = None


class OIDCTokenResponse(BaseModel):
    """Minimum successful token-endpoint response."""

    model_config = ConfigDict(extra="ignore")

    id_token: str = Field(min_length=16)


class IdentityProviderError(RuntimeError):
    """Stable, non-sensitive OIDC failure with an internal category."""

    def __init__(self, code: str = "oidc_authentication_failed") -> None:
        self.code = code
        super().__init__("Enterprise identity authentication failed")


class IdentityProvider(Protocol):
    """OIDC authorization-code provider contract used by the API layer."""

    async def start_authorization(self, redis: aioredis.Redis, tenant_id: str) -> str:
        """Persist request state and return the provider authorization URL."""
        ...

    async def authenticate_callback(
        self, redis: aioredis.Redis, *, state: str, code: str
    ) -> tuple[ExternalIdentity, str]:
        """Consume callback state, exchange code, and validate the ID token."""
        ...


class OIDCClient:
    """Standards-based OIDC client with bounded in-process metadata caches."""

    def __init__(
        self,
        *,
        issuer: str,
        client_id: str,
        redirect_uri: str,
        provider: str = "oidc",
        client_secret: str = "",
        allowed_algorithms: tuple[str, ...] = ("RS256",),
        timeout_seconds: float = 5.0,
        metadata_cache_seconds: int = 3600,
        state_ttl_seconds: int = 300,
        allow_insecure_http: bool = False,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if not issuer or not client_id or not redirect_uri:
            raise IdentityProviderError("oidc_not_configured")
        if not allowed_algorithms or not set(allowed_algorithms).issubset(
            SUPPORTED_ASYMMETRIC_ALGORITHMS
        ):
            raise IdentityProviderError("oidc_algorithms_missing")
        self._allow_insecure_http = allow_insecure_http and settings.ENVIRONMENT != "production"
        self._validate_url(issuer, "issuer")
        self._validate_url(redirect_uri, "redirect URI", allow_loopback=True)
        self.issuer = issuer
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.provider = provider
        self._client_secret = client_secret
        self._allowed_algorithms = allowed_algorithms
        self._timeout_seconds = timeout_seconds
        self._metadata_cache_seconds = metadata_cache_seconds
        self._state_ttl_seconds = state_ttl_seconds
        self._http_client = http_client
        self._discovery: tuple[float, OIDCDiscoveryDocument] | None = None
        self._jwks: tuple[float, OIDCJWKSet] | None = None
        self._cache_lock = asyncio.Lock()

    @classmethod
    def from_settings(cls) -> "OIDCClient":
        """Build the generic provider from canonical application settings."""
        if not settings.OIDC_ENABLED:
            raise IdentityProviderError("oidc_disabled")
        return cls(
            issuer=settings.OIDC_ISSUER,
            client_id=settings.OIDC_CLIENT_ID,
            client_secret=settings.OIDC_CLIENT_SECRET.get_secret_value(),
            redirect_uri=settings.OIDC_REDIRECT_URI,
            provider=settings.OIDC_PROVIDER_NAME,
            allowed_algorithms=tuple(settings.OIDC_ALLOWED_ALGORITHMS),
            timeout_seconds=settings.OIDC_TIMEOUT_SECONDS,
            metadata_cache_seconds=settings.OIDC_METADATA_CACHE_SECONDS,
            state_ttl_seconds=settings.OIDC_STATE_TTL_SECONDS,
            allow_insecure_http=settings.OIDC_ALLOW_INSECURE_HTTP,
        )

    async def start_authorization(self, redis: aioredis.Redis, tenant_id: str) -> str:
        """Create state, nonce, and PKCE S256 material for an authorization request."""
        validated_tenant = validate_tenant_id(tenant_id)
        discovery = await self.get_discovery()
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        code_verifier = secrets.token_urlsafe(64)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode("ascii")).digest())
            .rstrip(b"=")
            .decode("ascii")
        )
        login_state = OIDCLoginState(
            tenant_id=validated_tenant,
            nonce=nonce,
            code_verifier=code_verifier,
        )
        try:
            await redis.setex(
                self._state_key(state),
                self._state_ttl_seconds,
                login_state.model_dump_json(),
            )
        except aioredis.RedisError as error:
            raise IdentityProviderError("oidc_state_unavailable") from error
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "scope": "openid profile email",
                "state": state,
                "nonce": nonce,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
        return f"{discovery.authorization_endpoint}?{query}"

    async def authenticate_callback(
        self, redis: aioredis.Redis, *, state: str, code: str
    ) -> tuple[ExternalIdentity, str]:
        """Atomically consume state, exchange the code, and validate the ID token."""
        if not state or not code:
            raise IdentityProviderError("oidc_callback_invalid")
        try:
            raw_state = await redis.getdel(self._state_key(state))
        except aioredis.RedisError as error:
            raise IdentityProviderError("oidc_state_unavailable") from error
        if raw_state is None:
            raise IdentityProviderError("oidc_state_invalid")
        try:
            login_state = OIDCLoginState.model_validate_json(raw_state)
            validate_tenant_id(login_state.tenant_id)
        except (ValidationError, ValueError) as error:
            raise IdentityProviderError("oidc_state_invalid") from error

        discovery = await self.get_discovery()
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "code_verifier": login_state.code_verifier,
        }
        if self._client_secret:
            data["client_secret"] = self._client_secret
        token_response = await self._post_token(discovery.token_endpoint, data)
        identity = await self.validate_id_token(
            token_response.id_token,
            expected_nonce=login_state.nonce,
        )
        return identity, login_state.tenant_id

    async def get_discovery(self, *, force_refresh: bool = False) -> OIDCDiscoveryDocument:
        """Return validated provider metadata from a bounded cache."""
        now = time.monotonic()
        if not force_refresh and self._discovery is not None and self._discovery[0] > now:
            return self._discovery[1]
        async with self._cache_lock:
            now = time.monotonic()
            if not force_refresh and self._discovery is not None and self._discovery[0] > now:
                return self._discovery[1]
            url = f"{self.issuer.rstrip('/')}/.well-known/openid-configuration"
            payload = await self._get_json(url, "oidc_discovery_failed")
            try:
                discovery = OIDCDiscoveryDocument.model_validate(payload)
            except ValidationError as error:
                raise IdentityProviderError("oidc_discovery_invalid") from error
            if discovery.issuer != self.issuer:
                raise IdentityProviderError("oidc_issuer_mismatch")
            self._validate_url(discovery.authorization_endpoint, "authorization endpoint")
            self._validate_url(discovery.token_endpoint, "token endpoint")
            self._validate_url(discovery.jwks_uri, "JWKS endpoint")
            self._discovery = (now + self._metadata_cache_seconds, discovery)
            return discovery

    async def validate_id_token(
        self, id_token: str, *, expected_nonce: str | None
    ) -> ExternalIdentity:
        """Validate signature and OIDC security claims using configured algorithms."""
        try:
            header = jwt.get_unverified_header(id_token)
        except jwt.InvalidTokenError as error:
            raise IdentityProviderError("oidc_token_invalid") from error
        kid = header.get("kid")
        algorithm = header.get("alg")
        if not isinstance(kid, str) or not kid:
            raise IdentityProviderError("oidc_token_kid_missing")
        if not isinstance(algorithm, str) or algorithm not in self._allowed_algorithms:
            raise IdentityProviderError("oidc_token_algorithm_rejected")

        jwk = await self._key_for_id(kid)
        if jwk.use not in {None, "sig"} or jwk.alg not in {None, algorithm}:
            raise IdentityProviderError("oidc_token_key_rejected")
        try:
            signing_key = jwt.PyJWK.from_dict(
                jwk.model_dump(exclude_none=True), algorithm=algorithm
            )
            payload = jwt.decode(
                id_token,
                signing_key,
                algorithms=list(self._allowed_algorithms),
                audience=self.client_id,
                issuer=self.issuer,
                options={"require": ["iss", "sub", "aud", "exp", "iat"]},
                leeway=settings.OIDC_CLOCK_SKEW_SECONDS,
            )
            claims = OIDCTokenClaims.model_validate(payload)
        except (jwt.InvalidTokenError, ValidationError, ValueError) as error:
            raise IdentityProviderError("oidc_token_invalid") from error
        if expected_nonce is not None and (
            claims.nonce is None or not compare_digest(claims.nonce, expected_nonce)
        ):
            raise IdentityProviderError("oidc_nonce_invalid")
        return ExternalIdentity(
            provider=self.provider,
            issuer=claims.iss,
            subject=claims.sub,
            email=claims.email,
            email_verified=claims.email_verified,
            display_name=claims.name,
            authentication_time=claims.auth_time,
        )

    async def _key_for_id(self, kid: str) -> OIDCJWK:
        jwks = await self._get_jwks()
        key = next((candidate for candidate in jwks.keys if candidate.kid == kid), None)
        if key is not None:
            return key
        jwks = await self._get_jwks(force_refresh=True)
        key = next((candidate for candidate in jwks.keys if candidate.kid == kid), None)
        if key is None:
            raise IdentityProviderError("oidc_token_key_unknown")
        return key

    async def _get_jwks(self, *, force_refresh: bool = False) -> OIDCJWKSet:
        now = time.monotonic()
        if not force_refresh and self._jwks is not None and self._jwks[0] > now:
            return self._jwks[1]
        discovery = await self.get_discovery()
        async with self._cache_lock:
            now = time.monotonic()
            if not force_refresh and self._jwks is not None and self._jwks[0] > now:
                return self._jwks[1]
            payload = await self._get_json(discovery.jwks_uri, "oidc_jwks_failed")
            try:
                jwks = OIDCJWKSet.model_validate(payload)
            except ValidationError as error:
                raise IdentityProviderError("oidc_jwks_invalid") from error
            self._jwks = (now + self._metadata_cache_seconds, jwks)
            return jwks

    async def _get_json(self, url: str, failure_code: str) -> object:
        client = self._http_client or httpx.AsyncClient(timeout=self._timeout_seconds)
        owns_client = self._http_client is None
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, json.JSONDecodeError, ValueError) as error:
            raise IdentityProviderError(failure_code) from error
        finally:
            if owns_client:
                await client.aclose()

    async def _post_token(self, url: str, data: dict[str, str]) -> OIDCTokenResponse:
        client = self._http_client or httpx.AsyncClient(timeout=self._timeout_seconds)
        owns_client = self._http_client is None
        try:
            response = await client.post(url, data=data)
            response.raise_for_status()
            return OIDCTokenResponse.model_validate(response.json())
        except (httpx.HTTPError, json.JSONDecodeError, ValueError, ValidationError) as error:
            raise IdentityProviderError("oidc_code_exchange_failed") from error
        finally:
            if owns_client:
                await client.aclose()

    def _state_key(self, state: str) -> str:
        state_hash = hashlib.sha256(state.encode("utf-8")).hexdigest()
        return namespaced_system_key(f"auth:oidc:state:{state_hash}")

    def _validate_url(self, url: str, label: str, *, allow_loopback: bool = False) -> None:
        parsed = urlparse(url)
        if parsed.scheme == "https" and parsed.netloc:
            return
        is_loopback = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if (
            parsed.scheme == "http"
            and parsed.netloc
            and (
                self._allow_insecure_http
                or (allow_loopback and is_loopback and settings.ENVIRONMENT != "production")
            )
        ):
            return
        raise IdentityProviderError(f"oidc_{label.replace(' ', '_')}_invalid")


@lru_cache(maxsize=1)
def get_identity_provider() -> IdentityProvider:
    """Return the process-wide configured OIDC client and its metadata caches."""
    return OIDCClient.from_settings()
