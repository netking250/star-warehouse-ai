"""Durable issuer/subject binding tests for enterprise identity."""

import asyncio
import uuid

import pytest
from sqlmodel import select

from app.core.config import settings
from app.core.database import async_session_maker
from app.models.external_identity import ExternalIdentity as ExternalIdentityBinding
from app.models.user import User
from app.services.identity_provider import ExternalIdentity
from app.services.identity_service import IdentityAuthenticationError, IdentityService

ISSUER = "https://idp.example.com/realms/enterprise"


def _identity(
    *,
    issuer: str = ISSUER,
    subject: str = "employee-123",
    email: str | None = "person@example.com",
    email_verified: bool = True,
) -> ExternalIdentity:
    return ExternalIdentity(
        provider="enterprise-oidc",
        issuer=issuer,
        subject=subject,
        email=email,
        email_verified=email_verified,
    )


async def _create_user(tenant_id: str, *, email: str, is_active: bool = True) -> User:
    unique = uuid.uuid4().hex[:10]
    async with async_session_maker() as session, session.begin():
        user = User(
            tenant_id=tenant_id,
            username=f"oidc_{unique}",
            password_hash=User.hash_password("local-password"),
            email=email,
            full_name="OIDC Test User",
            is_active=is_active,
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
        return user


@pytest.mark.asyncio
async def test_oidc_exact_issuer_subject_ignores_changed_email(
    tenant_context: str, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "OIDC_ISSUER", ISSUER)
    monkeypatch.setattr(settings, "OIDC_LINK_VERIFIED_EMAIL", False)
    user = await _create_user(tenant_context, email="old@example.com")
    assert user.id is not None
    async with async_session_maker() as session, session.begin():
        session.add(
            ExternalIdentityBinding(
                tenant_id=tenant_context,
                user_id=user.id,
                provider="enterprise-oidc",
                issuer=ISSUER,
                subject="employee-123",
                email_at_link_time="old@example.com",
            )
        )

    async with async_session_maker() as session, session.begin():
        result = await IdentityService().authenticate_oidc(
            session,
            _identity(email="new@example.com"),
            tenant_id=tenant_context,
        )

    assert result.user.id == user.id
    assert result.principal.subject == "employee-123"


@pytest.mark.asyncio
async def test_oidc_same_email_from_different_issuer_cannot_hijack(
    tenant_context: str, monkeypatch
) -> None:
    attacker_issuer = "https://attacker.example.com"
    monkeypatch.setattr(settings, "OIDC_ISSUER", attacker_issuer)
    monkeypatch.setattr(settings, "OIDC_LINK_VERIFIED_EMAIL", True)
    user = await _create_user(tenant_context, email="person@example.com")
    assert user.id is not None
    async with async_session_maker() as session, session.begin():
        session.add(
            ExternalIdentityBinding(
                tenant_id=tenant_context,
                user_id=user.id,
                provider="trusted-original",
                issuer=ISSUER,
                subject="original-subject",
                email_at_link_time="person@example.com",
            )
        )

    async with async_session_maker() as session, session.begin():
        with pytest.raises(IdentityAuthenticationError) as error:
            await IdentityService().authenticate_oidc(
                session,
                _identity(issuer=attacker_issuer, subject="attacker"),
                tenant_id=tenant_context,
            )

    assert error.value.code == "oidc_cross_issuer_link_rejected"


@pytest.mark.asyncio
async def test_oidc_unverified_email_cannot_first_link(tenant_context: str, monkeypatch) -> None:
    monkeypatch.setattr(settings, "OIDC_ISSUER", ISSUER)
    monkeypatch.setattr(settings, "OIDC_LINK_VERIFIED_EMAIL", True)
    await _create_user(tenant_context, email="person@example.com")

    async with async_session_maker() as session, session.begin():
        with pytest.raises(IdentityAuthenticationError) as error:
            await IdentityService().authenticate_oidc(
                session,
                _identity(email_verified=False),
                tenant_id=tenant_context,
            )

    assert error.value.code == "oidc_verified_email_required"


@pytest.mark.asyncio
async def test_oidc_disabled_local_user_is_rejected_even_when_bound(
    tenant_context: str, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "OIDC_ISSUER", ISSUER)
    user = await _create_user(tenant_context, email="disabled@example.com", is_active=False)
    assert user.id is not None
    async with async_session_maker() as session, session.begin():
        session.add(
            ExternalIdentityBinding(
                tenant_id=tenant_context,
                user_id=user.id,
                provider="enterprise-oidc",
                issuer=ISSUER,
                subject="disabled-subject",
                email_at_link_time="disabled@example.com",
            )
        )

    async with async_session_maker() as session, session.begin():
        with pytest.raises(IdentityAuthenticationError) as error:
            await IdentityService().authenticate_oidc(
                session,
                _identity(subject="disabled-subject", email="disabled@example.com"),
                tenant_id=tenant_context,
            )

    assert error.value.code == "oidc_user_inactive"


@pytest.mark.asyncio
async def test_oidc_concurrent_first_link_creates_one_binding(
    tenant_context: str, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "OIDC_ISSUER", ISSUER)
    monkeypatch.setattr(settings, "OIDC_LINK_VERIFIED_EMAIL", True)
    user = await _create_user(tenant_context, email="person@example.com")

    async def authenticate_once() -> int:
        async with async_session_maker() as session, session.begin():
            result = await IdentityService().authenticate_oidc(
                session,
                _identity(),
                tenant_id=tenant_context,
            )
            assert result.user.id is not None
            return result.user.id

    user_ids = await asyncio.gather(authenticate_once(), authenticate_once())

    async with async_session_maker() as session:
        bindings = (
            await session.exec(
                select(ExternalIdentityBinding).where(
                    ExternalIdentityBinding.issuer == ISSUER,
                    ExternalIdentityBinding.subject == "employee-123",
                )
            )
        ).all()
    assert user_ids == [user.id, user.id]
    assert len(bindings) == 1


@pytest.mark.asyncio
async def test_oidc_binding_does_not_create_access_in_another_tenant(
    tenant_context: str, active_tenant: str, monkeypatch
) -> None:
    assert tenant_context == active_tenant
    monkeypatch.setattr(settings, "OIDC_ISSUER", ISSUER)
    monkeypatch.setattr(settings, "OIDC_LINK_VERIFIED_EMAIL", False)
    user = await _create_user(tenant_context, email="person@example.com")
    assert user.id is not None
    async with async_session_maker() as session, session.begin():
        session.add(
            ExternalIdentityBinding(
                tenant_id=tenant_context,
                user_id=user.id,
                provider="enterprise-oidc",
                issuer=ISSUER,
                subject="employee-123",
                email_at_link_time="person@example.com",
            )
        )

    with pytest.raises(IdentityAuthenticationError):
        async with async_session_maker() as session, session.begin():
            await IdentityService().authenticate_oidc(
                session,
                _identity(),
                tenant_id="default",
            )
