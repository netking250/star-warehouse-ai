"""Canonical tenant-aware roles, capabilities, and policy decisions."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.tenancy import TenantContext
from app.models.user import User


class Role(StrEnum):
    """Application roles that group capability-oriented scopes."""

    SUPER_ADMIN = "super_admin"
    IDENTITY_MANAGER = "identity_manager"
    KNOWLEDGE_ADMIN = "knowledge_admin"
    SERVICE_SUPERVISOR = "service_supervisor"
    REVIEWER = "reviewer"
    ANALYST = "analyst"
    AUDITOR = "auditor"
    CUSTOMER = "customer"


class Scope(StrEnum):
    """Canonical application capabilities."""

    CHAT_USE = "chat.use"
    PROFILE_READ = "profile.read"
    FEEDBACK_WRITE = "feedback.write"
    ORDERS_READ = "orders.read"
    ORDERS_WRITE = "orders.write"
    REFUNDS_READ = "refunds.read"
    REFUNDS_APPROVE = "refunds.approve"
    KNOWLEDGE_READ = "knowledge.read"
    KNOWLEDGE_WRITE = "knowledge.write"
    REVIEWS_READ = "reviews.read"
    REVIEWS_APPROVE = "reviews.approve"
    CONVERSATIONS_READ = "conversations.read"
    EVALUATION_READ = "evaluation.read"
    EVALUATION_MANAGE = "evaluation.manage"
    OPERATIONS_READ = "operations.read"
    OPERATIONS_MANAGE = "operations.manage"
    AUDIT_READ = "audit.read"
    COMPLIANCE_READ = "compliance.read"
    COMPLIANCE_MANAGE = "compliance.manage"
    EXPORTS_REQUEST = "exports.request"
    EXPORTS_APPROVE = "exports.approve"
    IDENTITY_READ = "identity.read"
    IDENTITY_MANAGE = "identity.manage"


_ROLE_SCOPES: dict[Role, frozenset[Scope]] = {
    Role.SUPER_ADMIN: frozenset(Scope),
    Role.IDENTITY_MANAGER: frozenset({Scope.IDENTITY_READ, Scope.IDENTITY_MANAGE}),
    Role.KNOWLEDGE_ADMIN: frozenset({Scope.KNOWLEDGE_READ, Scope.KNOWLEDGE_WRITE}),
    Role.SERVICE_SUPERVISOR: frozenset(
        {
            Scope.CONVERSATIONS_READ,
            Scope.REVIEWS_READ,
            Scope.REVIEWS_APPROVE,
            Scope.REFUNDS_READ,
            Scope.REFUNDS_APPROVE,
            Scope.OPERATIONS_READ,
            Scope.EXPORTS_REQUEST,
        }
    ),
    Role.REVIEWER: frozenset(
        {Scope.REVIEWS_READ, Scope.REVIEWS_APPROVE, Scope.REFUNDS_READ, Scope.REFUNDS_APPROVE}
    ),
    Role.ANALYST: frozenset(
        {
            Scope.OPERATIONS_READ,
            Scope.EVALUATION_READ,
            Scope.CONVERSATIONS_READ,
            Scope.EXPORTS_REQUEST,
        }
    ),
    Role.AUDITOR: frozenset(
        {
            Scope.AUDIT_READ,
            Scope.CONVERSATIONS_READ,
            Scope.IDENTITY_READ,
            Scope.COMPLIANCE_READ,
            Scope.EXPORTS_APPROVE,
        }
    ),
    Role.CUSTOMER: frozenset(
        {
            Scope.CHAT_USE,
            Scope.PROFILE_READ,
            Scope.FEEDBACK_WRITE,
            Scope.ORDERS_READ,
            Scope.ORDERS_WRITE,
        }
    ),
}

_LEGACY_SCOPE_ALIASES: dict[str, str] = {
    "chat.use": "chat:use",
    "profile.read": "profile:read",
    "knowledge.read": "knowledge:read",
    "knowledge.write": "knowledge:write",
    "reviews.read": "review:read",
    "reviews.approve": "review:decide",
    "conversations.read": "conversation:read",
    "evaluation.read": "evaluation:read",
    "operations.read": "analytics:read",
    "audit.read": "audit:read",
}


class AuthorizationReason(StrEnum):
    """Stable internal reason codes for policy decisions."""

    ALLOW = "ALLOW"
    NOT_AUTHENTICATED = "NOT_AUTHENTICATED"
    TENANT_MEMBERSHIP_REQUIRED = "TENANT_MEMBERSHIP_REQUIRED"
    ACCOUNT_DISABLED = "ACCOUNT_DISABLED"
    ROLE_REQUIRED = "ROLE_REQUIRED"
    SCOPE_REQUIRED = "SCOPE_REQUIRED"
    RESOURCE_FORBIDDEN = "RESOURCE_FORBIDDEN"
    AUTHORIZATION_STATE_INVALID = "AUTHORIZATION_STATE_INVALID"


@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipal:
    """Cryptographically authenticated local application principal."""

    tenant_id: str
    user_id: int
    session_id: str
    correlation_id: str
    token_id: str
    expires_at: int = field(default=0, compare=False)
    token_roles: frozenset[str] = field(default_factory=frozenset, compare=False)
    token_scopes: frozenset[str] = field(default_factory=frozenset, compare=False)


@dataclass(frozen=True, slots=True)
class AuthorizationContext:
    """Current tenant membership and effective application authority."""

    principal: AuthenticatedPrincipal
    tenant: TenantContext
    roles: frozenset[Role]
    scopes: frozenset[str]

    @property
    def tenant_id(self) -> str:
        """Return the trusted current tenant ID."""
        return self.tenant.tenant_id

    @property
    def user_id(self) -> int:
        """Return the current local user ID."""
        return self.principal.user_id

    @property
    def session_id(self) -> str:
        """Return the authenticated session identifier."""
        return self.principal.session_id

    @property
    def correlation_id(self) -> str:
        """Return the request correlation identifier."""
        return self.principal.correlation_id

    @property
    def token_id(self) -> str:
        """Return the authenticated token identifier."""
        return self.principal.token_id

    @property
    def expires_at(self) -> int:
        """Return the authenticated token expiry."""
        return self.principal.expires_at

    def has_role(self, role: Role) -> bool:
        """Return whether the current local assignment contains the role."""
        return Role.SUPER_ADMIN in self.roles or role in self.roles

    def has_scope(self, scope: Scope | str) -> bool:
        """Return whether current local role state grants a capability."""
        return "*" in self.scopes or str(scope) in self.scopes


@dataclass(frozen=True, slots=True)
class AuthorizationPolicy:
    """A route or use-case authorization requirement."""

    scopes: frozenset[Scope] = field(default_factory=frozenset)
    roles: frozenset[Role] = field(default_factory=frozenset)
    require_all_scopes: bool = True


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    """Normalized policy result retained for structured security evidence."""

    allowed: bool
    reason: AuthorizationReason
    required_scopes: frozenset[Scope] = field(default_factory=frozenset)
    required_roles: frozenset[Role] = field(default_factory=frozenset)


class AuthorizationResolutionError(Exception):
    """Raised when current local authorization state cannot establish membership."""

    def __init__(self, reason: AuthorizationReason) -> None:
        super().__init__(reason.value)
        self.reason = reason


def role_for_user(user: User) -> Role:
    """Return the single current application role stored on a tenant user."""
    if user.is_admin:
        return Role.SUPER_ADMIN
    try:
        return Role(user.role)
    except ValueError as error:
        raise AuthorizationResolutionError(
            AuthorizationReason.AUTHORIZATION_STATE_INVALID
        ) from error


def scopes_for_roles(
    roles: Iterable[Role | str], *, include_legacy_aliases: bool = True
) -> frozenset[str]:
    """Return capabilities granted by application roles.

    Colon-delimited aliases remain only for response/token compatibility. Route policies use the
    canonical dotted vocabulary, and current database role state is always resolved first.
    """
    normalized = frozenset(Role(role) for role in roles)
    if not normalized:
        raise ValueError("At least one role is required")
    if Role.SUPER_ADMIN in normalized:
        return frozenset({"*"})
    canonical = {scope.value for role in normalized for scope in _ROLE_SCOPES[role]}
    if include_legacy_aliases:
        canonical.update(
            alias for scope, alias in _LEGACY_SCOPE_ALIASES.items() if scope in canonical
        )
    return frozenset(canonical)


async def resolve_authorization_context(
    session: AsyncSession,
    principal: AuthenticatedPrincipal,
    tenant: TenantContext,
) -> AuthorizationContext:
    """Load current tenant membership and role state from PostgreSQL.

    The tenant-owned ``User`` row is the existing local account and membership record. JWT role,
    scope, and upstream OIDC claims are deliberately ignored when computing effective authority.
    """
    result = await session.exec(
        select(User).where(User.id == principal.user_id, User.tenant_id == tenant.tenant_id)
    )
    user = result.one_or_none()
    if user is None:
        raise AuthorizationResolutionError(AuthorizationReason.TENANT_MEMBERSHIP_REQUIRED)
    if not user.is_active:
        raise AuthorizationResolutionError(AuthorizationReason.ACCOUNT_DISABLED)
    role = role_for_user(user)
    roles = frozenset({role})
    return AuthorizationContext(
        principal=principal,
        tenant=tenant,
        roles=roles,
        scopes=scopes_for_roles(roles),
    )


def authorize(context: AuthorizationContext, policy: AuthorizationPolicy) -> AuthorizationDecision:
    """Evaluate a capability/role policy against current local authorization state."""
    if policy.roles and not any(context.has_role(role) for role in policy.roles):
        return AuthorizationDecision(
            allowed=False,
            reason=AuthorizationReason.ROLE_REQUIRED,
            required_scopes=policy.scopes,
            required_roles=policy.roles,
        )
    if policy.scopes:
        checks = tuple(context.has_scope(scope) for scope in policy.scopes)
        scopes_allowed = all(checks) if policy.require_all_scopes else any(checks)
        if not scopes_allowed:
            return AuthorizationDecision(
                allowed=False,
                reason=AuthorizationReason.SCOPE_REQUIRED,
                required_scopes=policy.scopes,
                required_roles=policy.roles,
            )
    return AuthorizationDecision(
        allowed=True,
        reason=AuthorizationReason.ALLOW,
        required_scopes=policy.scopes,
        required_roles=policy.roles,
    )
