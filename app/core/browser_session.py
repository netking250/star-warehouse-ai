"""Secure browser credential transport, CSRF, and trusted-origin primitives."""

import base64
import hashlib
import hmac
import json
import secrets
from collections.abc import Mapping
from datetime import UTC, datetime
from urllib.parse import urlsplit

from fastapi import Response
from pydantic import BaseModel, ValidationError

from app.authorization.policy import AuthenticatedPrincipal, AuthorizationContext
from app.core.config import settings
from app.core.utils import utc_now

CSRF_HEADER_NAME = "X-CSRF-Token"
_CSRF_CONTEXT = b"star-warehouse-ai:browser-csrf:v1:"


class _CsrfClaims(BaseModel):
    """Signed CSRF claims bound to one application-token session."""

    session_id: str
    token_id: str
    expires_at: int
    nonce: str


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.b64decode(value + padding, altchars=b"-_", validate=True)


def _csrf_signature(payload: bytes) -> bytes:
    key = settings.SECRET_KEY.get_secret_value().encode("utf-8")
    return hmac.new(key, _CSRF_CONTEXT + payload, hashlib.sha256).digest()


def issue_csrf_token(context: AuthenticatedPrincipal | AuthorizationContext) -> str:
    """Issue an in-memory browser CSRF token bound to the current auth token and session."""
    claims = _CsrfClaims(
        session_id=context.session_id,
        token_id=context.token_id,
        expires_at=context.expires_at,
        nonce=secrets.token_urlsafe(24),
    )
    payload = claims.model_dump_json().encode("utf-8")
    return f"{_base64url_encode(payload)}.{_base64url_encode(_csrf_signature(payload))}"


def csrf_token_is_valid(
    token: str | None,
    context: AuthenticatedPrincipal | AuthorizationContext,
) -> bool:
    """Return whether a CSRF token is authentic, unexpired, and session-bound."""
    if not token:
        return False
    try:
        encoded_payload, encoded_signature = token.split(".", 1)
        payload = _base64url_decode(encoded_payload)
        supplied_signature = _base64url_decode(encoded_signature)
        if not hmac.compare_digest(supplied_signature, _csrf_signature(payload)):
            return False
        claims = _CsrfClaims.model_validate(json.loads(payload))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError, ValidationError):
        return False
    now = int(utc_now().timestamp())
    return (
        claims.expires_at >= now
        and claims.expires_at == context.expires_at
        and secrets.compare_digest(claims.session_id, context.session_id)
        and secrets.compare_digest(claims.token_id, context.token_id)
    )


def _origin_from_url(value: str) -> str | None:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    if parsed.username is not None or parsed.password is not None:
        return None
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def origin_is_trusted(value: str | None) -> bool:
    """Match a browser Origin or Referer origin against exact configured CORS origins."""
    if not value:
        return False
    candidate = _origin_from_url(value)
    if candidate is None:
        return False
    trusted = {_origin_from_url(origin) for origin in settings.CORS_ORIGINS}
    return candidate in trusted


def request_origin_is_trusted(headers: Mapping[str, str]) -> bool:
    """Validate Origin, falling back to Referer only when Origin is absent."""
    origin = headers.get("origin")
    if origin is not None:
        return origin_is_trusted(origin)
    return origin_is_trusted(headers.get("referer"))


def set_browser_auth_cookie(response: Response, token: str, *, expires_at: int) -> None:
    """Set the canonical host-only browser authentication cookie."""
    remaining_seconds = max(0, expires_at - int(utc_now().timestamp()))
    max_age = min(settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60, remaining_seconds)
    response.set_cookie(
        key=settings.BROWSER_AUTH_COOKIE_NAME,
        value=token,
        max_age=max_age,
        expires=datetime.fromtimestamp(expires_at, tz=UTC),
        path="/",
        secure=settings.BROWSER_AUTH_COOKIE_SECURE,
        httponly=True,
        samesite=settings.BROWSER_AUTH_COOKIE_SAMESITE,
    )


def clear_browser_auth_cookie(response: Response) -> None:
    """Expire the canonical browser authentication cookie with matching attributes."""
    response.delete_cookie(
        key=settings.BROWSER_AUTH_COOKIE_NAME,
        path="/",
        secure=settings.BROWSER_AUTH_COOKIE_SECURE,
        httponly=True,
        samesite=settings.BROWSER_AUTH_COOKIE_SAMESITE,
    )
