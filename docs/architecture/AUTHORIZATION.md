# Enterprise Authorization

T09 centralizes application authorization without changing T08 identity proof, T06/T07 tenant
selection and isolation, or the accepted T10 browser credential transport.

## Security boundaries

The request sequence is:

```text
T08 authenticated local identity
  -> signed application-token principal
  -> trusted T06 TenantContext
  -> current tenant-owned User membership
  -> current local role and effective scopes
  -> centralized route/resource policy
  -> business operation
  -> T07 PostgreSQL RLS
```

- **Authentication** proves which local `User` is making the request. Local-password and OIDC
  login both resolve to that same local identity. Upstream `roles`, `groups`, `realm_access`, and
  custom claims are not application authority.
- **Tenancy** resolves and validates the tenant carried by the application token. Production paths
  do not infer a default tenant.
- **Authorization** loads the current tenant-local `User` row and derives effective application
  authority from its current `role`, `is_admin`, and `is_active` state.
- **RLS** remains an independent database boundary after application authorization. Application
  roles never select a PostgreSQL capability role and never imply `SUPERUSER` or `BYPASSRLS`.

## Authoritative model

`app.authorization.policy` owns `Role`, the dotted `Scope` vocabulary, `AuthorizationContext`,
`AuthorizationPolicy`, reason-coded decisions, and the evaluator. The existing tenant-owned
`User` row is the membership record: a matching active row is required for the token's local user
and trusted tenant. A missing row denies with `TENANT_MEMBERSHIP_REQUIRED`; an inactive row denies
with `ACCOUNT_DISABLED`.

Each membership currently has one role. Roles group only capabilities used by current application
domains: chat/profile/feedback, orders, refunds, knowledge, reviews, conversations, evaluation,
operations, audit, compliance, sensitive export approval, and identity administration. `SUPER_ADMIN`
is retained as an application role with all application capabilities. The compatibility `is_admin`
column maps existing administrators deterministically to that role.

JWT `roles`, `scopes`, and `is_admin` remain compatibility snapshots for existing clients. They are
never used to calculate a protected request's effective authority. A protected HTTP or WebSocket
request always reloads the current membership and role from PostgreSQL, so role removal or
membership disablement takes effect on the next request even while the JWT remains valid. T09 adds
no authorization cache.

## Policy enforcement

`app.authorization.route_inventory` is the single transport policy inventory. Each HTTP method
and WebSocket route template is explicitly classified as `PUBLIC`, `AUTHENTICATED`,
`TENANT_SCOPE_REQUIRED`, or `SYSTEM_INTERNAL`. Application startup and structural tests fail when
a route is unclassified; protected HTTP entries also fail when their dependency graph lacks the
canonical authorization seam.

HTTP business routes resolve current membership through `get_active_auth_context` and enforce the
inventory capability through `get_authorized_auth_context`. The legacy-named
`get_admin_user_id` is now only an adapter to that route-specific capability policy; it no longer
performs a blanket `SUPER_ADMIN` check. WebSocket helpers apply their inventory policies after the
same current membership lookup: customer chat requires `chat.use`, and the admin channel requires
`operations.read`.

Existing resource checks remain in domain services where capability alone is insufficient. T09
does not add a generic ABAC language. Cross-tenant resources continue to be hidden according to
their existing service/RLS 403-or-404 behavior.

## Route classification

The production inventory contains 127 HTTP method/routes and 2 WebSocket routes, with no unknown
entries at T11 implementation handoff.

Public application endpoints are local login, OIDC login initiation and callback, registration,
web-vitals intake, health, and static frontend assets/routes. `/me` and `/logout` require a current
authenticated membership. OpenAPI routes and the Prometheus mount are intentionally classified as
system/infrastructure endpoints and must be exposure-controlled by deployment configuration or
network policy.

Sensitive feedback export requests and execution require `exports.request`; approval decisions
require `exports.approve`, and retention inspection/execution require `compliance.read` or
`compliance.manage` respectively. Every compliance route is tenant-scoped and remains subject to
current membership authorization plus PostgreSQL RLS.

No production route remains blanket `SUPER_ADMIN`-only. `SUPER_ADMIN` remains intentionally
special inside authorization administration: only an existing tenant `SUPER_ADMIN` can grant that
role, and the final active tenant administrator cannot be demoted or disabled. All other route
access is capability based.

## Administration, audit, and transactions

The minimal backend administration API can list memberships/effective authority, replace one role,
and enable or disable a membership. Reads require `identity.read`; mutations require
`identity.manage`. Self-role and self-status changes are rejected, non-super administrators cannot
grant `SUPER_ADMIN`, and last-admin removal is rejected.

Role and membership mutations stage an `authorization_audit_events` row in the same caller-owned
database transaction as the changed `User`. The evidence records tenant, actor, target, action,
before/after state, decision, reason, and correlation ID. A rollback removes both the state change
and audit row. Ordinary denies use structured security logs with stable reason codes rather than
persisting a high-volume audit row for every denial. No token, credential, or upstream identity
payload is logged.

The audit table is tenant-owned and protected by the same forced-RLS policy and runtime/maintenance
role grants as the accepted T07 model. No asynchronous cache invalidation is needed because current
authority is read directly for each protected operation.

## Background work

Normal jobs consume the trusted `TaskContext` produced after an authorized request and do not replay
interactive JWT RBAC in every worker. Sensitive deferred commands retain actor, tenant,
correlation, and idempotency context for evidence; they do not trust copied JWT role/scope claims.
This preserves the T02/T03/T04 task, transaction, outbox, and delivery boundaries.

## Known limitations

- A tenant membership currently supports one application role and role-derived scopes; there are no
  per-user custom scope assignments or delegated role-administration rules.
- Membership provisioning across multiple tenants is an explicit local-account operation; email
  domain and OIDC issuer never imply membership.
- Prometheus and interactive API documentation exposure remains a deployment/network concern.
- T10's browser credential transport preserves these authorization semantics; T11 adds the
  capability-scoped compliance and export routes described above.
