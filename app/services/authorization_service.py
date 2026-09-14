"""Transactional tenant authorization administration service."""

from sqlmodel import col, func, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.authorization.policy import (
    AuthorizationContext,
    Role,
    role_for_user,
    scopes_for_roles,
)
from app.models.authorization_audit import AuthorizationAuditAction, AuthorizationAuditEvent
from app.models.user import User
from app.schemas.authorization import MembershipResponse


class AuthorizationTargetNotFoundError(Exception):
    """Raised when a target is not a member of the current tenant."""


class AuthorizationSelfChangeError(Exception):
    """Raised when an actor attempts to change their own authority or membership."""


class AuthorizationPrivilegeEscalationError(Exception):
    """Raised when an actor attempts to grant a protected role."""


class LastTenantAdministratorError(Exception):
    """Raised when a change would remove the final active tenant administrator."""


class AuthorizationService:
    """Manage current tenant role and membership state without owning commits."""

    async def list_memberships(
        self, session: AsyncSession, *, tenant_id: str
    ) -> list[MembershipResponse]:
        """Return current memberships visible inside the trusted tenant context."""
        users = (
            await session.exec(
                select(User).where(User.tenant_id == tenant_id).order_by(col(User.id))
            )
        ).all()
        return [self._response(user) for user in users]

    async def get_membership(
        self, session: AsyncSession, user_id: int, *, tenant_id: str
    ) -> MembershipResponse:
        """Return one current tenant membership."""
        user = await self._target(session, user_id, tenant_id=tenant_id)
        return self._response(user)

    async def assign_role(
        self,
        session: AsyncSession,
        *,
        actor: AuthorizationContext,
        target_user_id: int,
        new_role: Role,
    ) -> MembershipResponse:
        """Replace a member role and stage matching audit evidence atomically."""
        target = await self._target(session, target_user_id, tenant_id=actor.tenant_id, lock=True)
        previous_role = role_for_user(target)
        if actor.user_id == target_user_id and previous_role != new_role:
            raise AuthorizationSelfChangeError()
        if new_role is Role.SUPER_ADMIN and Role.SUPER_ADMIN not in actor.roles:
            raise AuthorizationPrivilegeEscalationError()
        if previous_role is Role.SUPER_ADMIN and new_role is not Role.SUPER_ADMIN:
            await self._protect_last_administrator(session, tenant_id=actor.tenant_id)

        target.role = new_role.value
        target.is_admin = new_role is Role.SUPER_ADMIN
        session.add(target)
        action = (
            AuthorizationAuditAction.ROLE_ASSIGNED
            if new_role is not Role.CUSTOMER
            else AuthorizationAuditAction.ROLE_REVOKED
        )
        session.add(
            AuthorizationAuditEvent(
                actor_user_id=actor.user_id,
                target_user_id=target_user_id,
                action=action,
                previous_role=previous_role.value,
                new_role=new_role.value,
                correlation_id=actor.correlation_id,
            )
        )
        await session.flush()
        return self._response(target)

    async def set_membership_active(
        self,
        session: AsyncSession,
        *,
        actor: AuthorizationContext,
        target_user_id: int,
        active: bool,
    ) -> MembershipResponse:
        """Enable or revoke one current tenant membership with atomic audit evidence."""
        target = await self._target(session, target_user_id, tenant_id=actor.tenant_id, lock=True)
        if actor.user_id == target_user_id and target.is_active != active:
            raise AuthorizationSelfChangeError()
        if not active and target.is_active and role_for_user(target) is Role.SUPER_ADMIN:
            await self._protect_last_administrator(session, tenant_id=actor.tenant_id)

        previous_active = target.is_active
        target.is_active = active
        session.add(target)
        session.add(
            AuthorizationAuditEvent(
                actor_user_id=actor.user_id,
                target_user_id=target_user_id,
                action=(
                    AuthorizationAuditAction.MEMBERSHIP_ENABLED
                    if active
                    else AuthorizationAuditAction.MEMBERSHIP_DISABLED
                ),
                previous_active=previous_active,
                new_active=active,
                correlation_id=actor.correlation_id,
            )
        )
        await session.flush()
        return self._response(target)

    async def _target(
        self,
        session: AsyncSession,
        user_id: int,
        *,
        tenant_id: str,
        lock: bool = False,
    ) -> User:
        statement = select(User).where(User.id == user_id, User.tenant_id == tenant_id)
        if lock:
            statement = statement.with_for_update()
        target = (await session.exec(statement)).one_or_none()
        if target is None:
            raise AuthorizationTargetNotFoundError()
        return target

    async def _protect_last_administrator(self, session: AsyncSession, *, tenant_id: str) -> None:
        active_admins = (
            await session.exec(
                select(func.count())
                .select_from(User)
                .where(
                    User.tenant_id == tenant_id,
                    col(User.is_active).is_(True),
                    or_(col(User.is_admin).is_(True), User.role == Role.SUPER_ADMIN.value),
                )
            )
        ).one()
        if active_admins <= 1:
            raise LastTenantAdministratorError()

    @staticmethod
    def _response(user: User) -> MembershipResponse:
        if user.id is None:
            raise RuntimeError("Persisted user is missing an identifier")
        role = role_for_user(user)
        scopes = sorted(
            scope
            for scope in scopes_for_roles({role}, include_legacy_aliases=False)
            if scope != "*"
        )
        if role is Role.SUPER_ADMIN:
            scopes = ["*"]
        return MembershipResponse(
            user_id=user.id,
            username=user.username,
            active=user.is_active,
            role=role,
            scopes=scopes,
        )
