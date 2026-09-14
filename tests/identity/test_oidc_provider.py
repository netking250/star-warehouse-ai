"""Cryptographic and authorization-code tests for the generic OIDC provider."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse

import httpx
import jwt
import pytest
import redis.asyncio as aioredis
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from jwt.algorithms import RSAAlgorithm

from app.services.identity_provider import (
    IdentityProviderError,
    OIDCClient,
    OIDCLoginState,
)

ISSUER = "https://idp.example.com/realms/enterprise"
CLIENT_ID = "star-warehouse-ai"
REDIRECT_URI = "https://app.example.com/api/v1/oidc/callback"


def _private_key() -> RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _jwk(private_key: RSAPrivateKey, kid: str = "key-1") -> dict[str, object]:
    value = json.loads(RSAAlgorithm.to_jwk(private_key.public_key()))
    value.update({"kid": kid, "alg": "RS256", "use": "sig"})
    return value


def _claims(*, now: datetime | None = None, **overrides: object) -> dict[str, object]:
    issued_at = int((now or datetime.now(UTC)).timestamp())
    claims: dict[str, object] = {
        "iss": ISSUER,
        "sub": "employee-123",
        "aud": CLIENT_ID,
        "iat": issued_at,
        "exp": issued_at + 300,
        "nonce": "expected-nonce",
        "email": "person@example.com",
        "email_verified": True,
        "name": "Example Person",
    }
    claims.update(overrides)
    return claims


def _token(private_key: RSAPrivateKey, claims: dict[str, object], kid: str = "key-1") -> str:
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": kid})


def _transport(
    *, jwks: list[dict[str, object]], id_token: str | None = None
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/.well-known/openid-configuration"):
            return httpx.Response(
                200,
                json={
                    "issuer": ISSUER,
                    "authorization_endpoint": f"{ISSUER}/protocol/openid-connect/auth",
                    "token_endpoint": f"{ISSUER}/protocol/openid-connect/token",
                    "jwks_uri": f"{ISSUER}/protocol/openid-connect/certs",
                },
            )
        if request.url.path.endswith("/certs"):
            return httpx.Response(200, json={"keys": jwks})
        if request.url.path.endswith("/token") and id_token is not None:
            return httpx.Response(200, json={"id_token": id_token})
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def _client(http_client: httpx.AsyncClient) -> OIDCClient:
    return OIDCClient(
        issuer=ISSUER,
        client_id=CLIENT_ID,
        redirect_uri=REDIRECT_URI,
        http_client=http_client,
    )


@pytest.mark.asyncio
async def test_oidc_valid_signed_token_returns_normalized_identity() -> None:
    private_key = _private_key()
    signed = _token(private_key, _claims())
    async with httpx.AsyncClient(transport=_transport(jwks=[_jwk(private_key)])) as http_client:
        identity = await _client(http_client).validate_id_token(
            signed, expected_nonce="expected-nonce"
        )

    assert identity.issuer == ISSUER
    assert identity.subject == "employee-123"
    assert str(identity.email) == "person@example.com"
    assert identity.email_verified is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("scenario", "sign_with_forged_key"),
    [
        ("wrong_issuer", False),
        ("wrong_audience", False),
        ("expired", False),
        ("future_nbf", False),
        ("missing_subject", False),
        ("forged_signature", True),
    ],
)
async def test_oidc_hostile_tokens_fail_closed(scenario: str, sign_with_forged_key: bool) -> None:
    now = datetime.now(UTC)
    now_epoch = int(now.timestamp())
    claims = _claims(now=now)
    if scenario == "wrong_issuer":
        claims["iss"] = "https://attacker.example.com"
    elif scenario == "wrong_audience":
        claims["aud"] = "wrong-client"
    elif scenario == "expired":
        claims["exp"] = now_epoch - 60
    elif scenario == "future_nbf":
        claims["nbf"] = now_epoch + 300
    elif scenario == "missing_subject":
        del claims["sub"]

    trusted_key = _private_key()
    signing_key = _private_key() if sign_with_forged_key else trusted_key
    signed = _token(signing_key, claims)
    async with httpx.AsyncClient(transport=_transport(jwks=[_jwk(trusted_key)])) as http_client:
        with pytest.raises(IdentityProviderError):
            await _client(http_client).validate_id_token(signed, expected_nonce="expected-nonce")


@pytest.mark.asyncio
async def test_oidc_nonce_mismatch_fails_closed() -> None:
    private_key = _private_key()
    signed = _token(private_key, _claims(nonce="different-nonce"))
    async with httpx.AsyncClient(transport=_transport(jwks=[_jwk(private_key)])) as http_client:
        with pytest.raises(IdentityProviderError) as error:
            await _client(http_client).validate_id_token(signed, expected_nonce="expected-nonce")

    assert error.value.code == "oidc_nonce_invalid"


@pytest.mark.asyncio
async def test_oidc_unknown_kid_refreshes_jwks_once() -> None:
    old_key = _private_key()
    rotated_key = _private_key()
    signed = _token(rotated_key, _claims(), kid="key-2")
    jwks_requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal jwks_requests
        if request.url.path.endswith("/.well-known/openid-configuration"):
            return httpx.Response(
                200,
                json={
                    "issuer": ISSUER,
                    "authorization_endpoint": f"{ISSUER}/auth",
                    "token_endpoint": f"{ISSUER}/token",
                    "jwks_uri": f"{ISSUER}/certs",
                },
            )
        if request.url.path.endswith("/certs"):
            jwks_requests += 1
            key = old_key if jwks_requests == 1 else rotated_key
            kid = "key-1" if jwks_requests == 1 else "key-2"
            return httpx.Response(200, json={"keys": [_jwk(key, kid)]})
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        identity = await _client(http_client).validate_id_token(
            signed, expected_nonce="expected-nonce"
        )

    assert identity.subject == "employee-123"
    assert jwks_requests == 2


@pytest.mark.asyncio
async def test_oidc_authorization_request_persists_state_nonce_and_pkce() -> None:
    private_key = _private_key()
    redis = AsyncMock(spec=aioredis.Redis)
    redis.setex = AsyncMock()
    async with httpx.AsyncClient(transport=_transport(jwks=[_jwk(private_key)])) as http_client:
        authorization_url = await _client(http_client).start_authorization(redis, "tenant-a")

    query = parse_qs(urlparse(authorization_url).query)
    assert query["response_type"] == ["code"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["state"]
    assert query["nonce"]
    assert redis.setex.await_args is not None
    stored = OIDCLoginState.model_validate_json(redis.setex.await_args.args[2])
    assert stored.tenant_id == "tenant-a"
    assert stored.nonce == query["nonce"][0]
    assert stored.code_verifier not in authorization_url


@pytest.mark.asyncio
async def test_oidc_callback_rejects_state_mismatch_before_code_exchange() -> None:
    private_key = _private_key()
    redis = AsyncMock(spec=aioredis.Redis)
    redis.getdel = AsyncMock(return_value=None)
    async with httpx.AsyncClient(transport=_transport(jwks=[_jwk(private_key)])) as http_client:
        with pytest.raises(IdentityProviderError) as error:
            await _client(http_client).authenticate_callback(
                redis,
                state="unknown-state-value",
                code="authorization-code",
            )

    assert error.value.code == "oidc_state_invalid"
