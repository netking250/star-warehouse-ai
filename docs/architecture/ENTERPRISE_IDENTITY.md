# Enterprise Identity

## Responsibility boundaries

Authentication answers **who the principal is**. Authorization (T09) answers **what the principal
may do**. Tenancy (T06/T07) answers **for which explicitly resolved tenant** an operation runs.
Browser token transport remains T10. A valid OIDC identity therefore grants neither a role nor a
tenant selection, and provider groups/roles are not mapped to application authority in T08.

## Authentication paths

Local login continues to validate the existing tenant-local username/password record and issue the
existing Star Warehouse application JWT. OIDC login uses authorization code flow with server-side
single-use state, nonce, and PKCE S256, then exchanges the code directly with the provider. The ID
token signature, configured algorithm, issuer, audience, expiry, optional not-before, and required
subject are validated through discovery and cached JWKS. An unknown `kid` causes one JWKS refresh.

After verification, both paths resolve a local `User`; OIDC then issues the same application JWT as
local login. This is a temporary browser-delivery compatibility path, not a second permanent token
architecture. HttpOnly/Secure/SameSite cookies, CSRF/Origin controls, and WebSocket transport are
explicitly T10.

## Durable external identity

`external_identities` binds one local user to a globally unique `(issuer, subject)` pair. Email is
stored only as link-time metadata. Once linked, later logins use only the verified issuer and
subject, so an upstream email change resolves the same user. A subject from another issuer is a
different identity and cannot claim the binding through a matching email.

The table is tenant-owned, protected by the existing ORM guards and forced PostgreSQL RLS, and has
a database uniqueness constraint for concurrent first login. The caller owns the outer transaction;
the link insert uses a savepoint so a concurrent uniqueness winner can be safely re-read.

## First-link policy

Automatic verified-email linking is disabled by default (`OIDC_LINK_VERIFIED_EMAIL=False`). When
an operator explicitly enables it, linking succeeds only for the configured trusted issuer, a
present `email` claim with strict Boolean `email_verified=true`, and exactly one active existing
local user with that email in the explicit tenant. Every other case fails closed. T08 never creates
a user, tenant, membership, role, scope, fake password, or super-admin assignment from OIDC claims.
Verified-email first-link also refuses a local user that already has any external binding, so a
second issuer cannot merge accounts through a shared email; such changes require an explicit
operator-controlled linking workflow outside this automatic path.

Externally bound users remain subject to local account state. Disabling the local user blocks OIDC
login. Raw provider ID/access/refresh tokens, authorization codes, and client secrets are neither
persisted nor logged.

## Local Keycloak demo

The canonical Compose file contains an optional `identity` profile using Keycloak as a demo of the
generic OIDC seam:

```powershell
docker compose --profile identity up -d keycloak
```

The imported realm is `star-warehouse`; the client is `star-warehouse-ai`; the demo user is
`oidc-demo` with verified email `keycloak-demo@example.com`. Values beginning with `dev-only-` are
local demo credentials and must be replaced on a shared host. Keycloak `start-dev`, HTTP issuer,
password grant, and imported demo credentials are not production guidance.

For the application, set `OIDC_ENABLED=True`, set the issuer to
`http://localhost:8081/realms/star-warehouse`, explicitly enable
`OIDC_ALLOW_INSECURE_HTTP=True` only for this local profile, and either pre-create the binding or
create exactly one active local user in the selected tenant with the demo email before temporarily
enabling verified-email linking.

The optional integration test proves real discovery, JWKS retrieval, Keycloak-signed token
validation, and local issuer/subject resolution. Separate deterministic tests prove callback state,
nonce, and PKCE behavior; no full browser E2E is claimed.

## Known limitations

Only one configured OIDC provider is active per application process. There is no SAML, SCIM,
application MFA integration, automatic user/tenant provisioning, provider-role authorization, or
SSO certification. T09 owns authorization policy; T10 owns secure browser session transport.
