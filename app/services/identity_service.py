"""Application service for resolving verified external identities to local users."""

import hashlib
import logging
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.utils import utc_now
from app.models.external_identity import ExternalIdentity as ExternalIdentityBinding
from app.models.user import User
from app.services.identity_provider import ExternalIdentity

logger = logging.getLogger(__name__)


class AuthenticationMethod(StrEnum):
    """Supported proof methods without authorization semantics."""

    LOCAL_PASSWORD = "local_password"
    OIDC = "oidc"


@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipal:
    """Normalized proof of who authenticated, independent of permission policy."""

    user_id: int
    authentication_method: AuthenticationMethod
    identity_provider: str
    issuer: str | None = None
    subject: str | None = None
    authentication_time: int | None = None


@dataclass(frozen=True, slots=True)
class IdentityAuthenticationResult:
    """Resolved local user and normalized authentication principal."""

    user: User
    principal: AuthenticatedPrincipal


class IdentityAuthenticationError(RuntimeError):
    """Fail-closed identity resolution error with a stable category."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("Enterprise identity is not linked to an active local account")


class IdentityService:
    """Resolve OIDC identities and transactionally create explicitly allowed links."""

    async def authenticate_local(self, user: User) -> IdentityAuthenticationResult:
        """Normalize an already verified local credential result without adding authority."""
        return IdentityAuthenticationResult(
            user=user,
            principal=AuthenticatedPrincipal(
                user_id=self._required_user_id(user),
                authentication_method=AuthenticationMethod.LOCAL_PASSWORD,
                identity_provider="local",
            ),
        )

    async def authenticate_oidc(
        self,
        session: AsyncSession,
        identity: ExternalIdentity,
        *,
        tenant_id: str,
    ) -> IdentityAuthenticationResult:
        """Resolve a verified issuer/subject pair to an active local user.

        The caller owns the outer transaction. A nested transaction contains the unique binding
        insert so a concurrent winner can be re-read without invalidating the caller transaction.
        """
        if identity.issuer != settings.OIDC_ISSUER:
            self._audit("oidc_identity_rejected", identity, reason="issuer_not_trusted")
            raise IdentityAuthenticationError("oidc_issuer_not_trusted")

        binding = await self._find_binding(session, identity)
        if binding is None:
            binding = await self._link_first_identity(
                session,
                identity,
                tenant_id=tenant_id,
            )
        try:
            user = await self._active_user_for_binding(session, binding, tenant_id=tenant_id)
        except IdentityAuthenticationError as error:
            self._audit("oidc_identity_rejected", identity, reason=error.code)
            raise
        binding.last_authenticated_at = utc_now()
        session.add(binding)
        await session.flush()
        self._audit("oidc_login_success", identity, user_id=user.id)
        return IdentityAuthenticationResult(
            user=user,
            principal=AuthenticatedPrincipal(
                user_id=self._required_user_id(user),
                authentication_method=AuthenticationMethod.OIDC,
                identity_provider=identity.provider,
                issuer=identity.issuer,
                subject=identity.subject,
                authentication_time=identity.authentication_time,
            ),
        )

    async def _find_binding(
        self, session: AsyncSession, identity: ExternalIdentity
    ) -> ExternalIdentityBinding | None:
        result = await session.exec(
            select(ExternalIdentityBinding).where(
                ExternalIdentityBinding.issuer == identity.issuer,
                ExternalIdentityBinding.subject == identity.subject,
            )
        )
        return result.one_or_none()

    async def _link_first_identity(
        self,
        session: AsyncSession,
        identity: ExternalIdentity,
        *,
        tenant_id: str,
    ) -> ExternalIdentityBinding:
        if not settings.OIDC_LINK_VERIFIED_EMAIL:
            self._audit("oidc_identity_rejected", identity, reason="linking_disabled")
            raise IdentityAuthenticationError("oidc_identity_not_linked")
        if identity.email is None or not identity.email_verified:
            self._audit("oidc_identity_rejected", identity, reason="verified_email_required")
            raise IdentityAuthenticationError("oidc_verified_email_required")

        result = await session.exec(
            select(User).where(User.tenant_id == tenant_id, User.email == str(identity.email))
        )
        candidates = result.all()
        if len(candidates) != 1:
            self._audit("oidc_identity_rejected", identity, reason="eligible_user_not_unique")
            raise IdentityAuthenticationError("oidc_link_target_invalid")
        user = candidates[0]
        if not user.is_active:
            self._audit("oidc_identity_rejected", identity, user_id=user.id, reason="user_inactive")
            raise IdentityAuthenticationError("oidc_user_inactive")
        user_id = self._required_user_id(user)
        existing_links = (
            await session.exec(
                select(ExternalIdentityBinding).where(
                    ExternalIdentityBinding.user_id == user_id,
                    ExternalIdentityBinding.tenant_id == tenant_id,
                )
            )
        ).all()
        if existing_links:
            self._audit(
                "oidc_identity_rejected", identity, user_id=user_id, reason="cross_issuer_link"
            )
            raise IdentityAuthenticationError("oidc_cross_issuer_link_rejected")
        binding = ExternalIdentityBinding(
            tenant_id=tenant_id,
            user_id=user_id,
            provider=identity.provider,
            issuer=identity.issuer,
            subject=identity.subject,
            email_at_link_time=str(identity.email),
        )
        try:
            async with session.begin_nested():
                session.add(binding)
                await session.flush()
        except IntegrityError:
            concurrent_binding = await self._find_binding(session, identity)
            if concurrent_binding is None or concurrent_binding.user_id != user_id:
                self._audit("oidc_identity_rejected", identity, reason="binding_conflict")
                raise IdentityAuthenticationError("oidc_identity_conflict") from None
            return concurrent_binding
        self._audit("oidc_identity_linked", identity, user_id=user_id)
        return binding

    async def _active_user_for_binding(
        self,
        session: AsyncSession,
        binding: ExternalIdentityBinding,
        *,
        tenant_id: str,
    ) -> User:
        result = await session.exec(
            select(User).where(User.id == binding.user_id, User.tenant_id == tenant_id)
        )
        user = result.one_or_none()
        if user is None:
            raise IdentityAuthenticationError("oidc_link_target_missing")
        if not user.is_active:
            raise IdentityAuthenticationError("oidc_user_inactive")
        return user

    @staticmethod
    def _required_user_id(user: User) -> int:
        if user.id is None:
            raise IdentityAuthenticationError("oidc_link_target_missing")
        return user.id

    @staticmethod
    def _audit(
        event: str,
        identity: ExternalIdentity,
        *,
        user_id: int | None = None,
        reason: str | None = None,
    ) -> None:
        logger.info(
            event,
            extra={
                "event": event,
                "identity_provider": identity.provider,
                "issuer": identity.issuer,
                "subject_hash": hashlib.sha256(identity.subject.encode("utf-8")).hexdigest()[:16],
                "user_id": user_id,
                "result": reason or "success",
            },
        )
