"""Tenant-aware application authorization policy."""

from app.authorization.policy import (
    AuthenticatedPrincipal,
    AuthorizationContext,
    AuthorizationDecision,
    AuthorizationPolicy,
    AuthorizationReason,
    Role,
    Scope,
    authorize,
    resolve_authorization_context,
    scopes_for_roles,
)

__all__ = [
    "AuthenticatedPrincipal",
    "AuthorizationContext",
    "AuthorizationDecision",
    "AuthorizationPolicy",
    "AuthorizationReason",
    "Role",
    "Scope",
    "authorize",
    "resolve_authorization_context",
    "scopes_for_roles",
]
