# Secure Browser Session

T10 changes how a browser carries an authenticated Star Warehouse application credential. It does
not change T08 identity proof, T09 authorization, tenant resolution, or PostgreSQL RLS.

## Transport model

Local browser login uses `POST /api/v1/browser/login`. The server creates the existing application
JWT, places it in the host-only `star_warehouse_session` cookie, and returns user/session metadata
without an access token. Browser JavaScript never reads the cookie. It restores authoritative login
state with `GET /api/v1/me` and keeps only the returned user data in memory.

`POST /api/v1/login` remains the compatibility contract for CLI, service-to-service, and API tools:
it returns the application token for `Authorization: Bearer`. Bearer-only requests do not require
browser CSRF state. Both transports decode into the same authenticated principal and continue
through current tenant membership, T09 policy, and RLS.

When both transports are present, different credentials are rejected. The same credential in both
places is treated as cookie authentication, so adding an Authorization header cannot bypass browser
CSRF controls.

## Cookie policy

The authentication cookie is `HttpOnly`, host-only (no `Domain`), `Path=/`, and explicitly
`SameSite=Lax`. `Secure=true` is the code default and mandatory in production. Plain-HTTP local
development may explicitly set `BROWSER_AUTH_COOKIE_SECURE=false`; there is no hostname-based
security downgrade. `SameSite=None` is rejected unless `Secure=true`.

The cookie expires at the application JWT expiry and its max-age never exceeds
`ACCESS_TOKEN_EXPIRE_MINUTES`. There is no application refresh-token architecture and T10 does not
add one. The stable cookie name is retained across explicit HTTP development and HTTPS production;
the `__Host-` prefix is therefore not forced, while host-only, Secure production behavior preserves
its relevant scope constraints.

## CSRF and Origin policy

`GET /api/v1/browser/csrf` returns a cryptographically signed, random token for in-memory frontend
use. Its signed claims contain the application token ID, login session ID, and credential expiry.
A token from Session A therefore cannot authorize Session B, and logout/new login makes the old
relationship unusable without adding a second server-side session framework.

Unsafe cookie-authenticated `POST`, `PUT`, `PATCH`, and `DELETE` requests require both the
`X-CSRF-Token` header and an exact trusted Origin. If Origin is absent, an exact-origin Referer is the
documented browser/proxy fallback; missing or untrusted evidence fails with a stable 403. Safe
`GET`/`HEAD` requests do not require CSRF. The configured `CORS_ORIGINS` list is the canonical trusted
browser-origin list. Credentialed CORS never uses `*`, and the CSRF header is explicitly allowed.

## OIDC completion

T08 still validates OIDC state, nonce, PKCE, issuer, audience, signature, and identity binding. On
success the callback creates the same application credential, sets the HttpOnly cookie, and returns
a 303 redirect to the configured local `BROWSER_POST_LOGIN_REDIRECT_PATH`. The path is configuration
validated as local and cannot contain a query, fragment, or scheme-relative target. No application
or provider token is placed in the URL or callback response body.

## Logout, rotation, and revocation

Cookie logout is `POST /api/v1/logout` and therefore requires CSRF and trusted-Origin evidence. The
server writes the existing Redis token revocation marker before clearing the cookie. A copied stale
cookie is rejected on the next request. Browser login and OIDC completion always create a fresh token
and session identifier and revoke a valid replaced browser credential. T09 still reloads current
membership and role state on every protected request, so permission removal denies the next request
even while the cookie remains cryptographically valid.

## WebSocket authentication

Browser WebSockets send the HttpOnly cookie automatically during the handshake. The backend requires
an exact trusted Origin for cookie authentication and then applies the existing T09 WebSocket route
scope (`chat.use` or `operations.read`) before accepting. Non-browser clients may keep using a Bearer
Authorization header where their WebSocket library supports it safely.

`token` and `access_token` query parameters are explicitly rejected, even if another credential is
also present. This prevents credentials from entering URLs, proxy/access logs, monitoring, browser
history, and screenshots. The frontend removes either parameter from constructed WebSocket URLs.

## Limits

HttpOnly reduces authentication-token theft by JavaScript. It does not eliminate XSS, malware,
browser compromise, or session riding, and T10 is not a full CSP, reverse-proxy, or browser-security
certification project.
