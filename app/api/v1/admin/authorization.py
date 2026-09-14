"""Tenant authorization administration endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.authorization.policy import AuthorizationContext
from app.core.database import get_session
from app.core.security import get_authorized_auth_context
from app.schemas.authorization import (
    MembershipResponse,
    MembershipStatusRequest,
    RoleAssignmentRequest,
)
from app.services.authorization_service import (
    AuthorizationPrivilegeEscalationError,
    AuthorizationSelfChangeError,
    AuthorizationService,
    AuthorizationTargetNotFoundError,
    LastTenantAdministratorError,
)

router = APIRouter()


@router.get("/memberships", response_model=list[MembershipResponse])
async def list_memberships(
    actor: AuthorizationContext = Depends(get_authorized_auth_context),
    session: AsyncSession = Depends(get_session),
    service: AuthorizationService = Depends(AuthorizationService),
) -> list[MembershipResponse]:
    """List current tenant memberships and effective local authority."""
    return await service.list_memberships(session, tenant_id=actor.tenant_id)


@router.get("/memberships/{user_id}", response_model=MembershipResponse)
async def get_membership(
    user_id: int,
    actor: AuthorizationContext = Depends(get_authorized_auth_context),
    session: AsyncSession = Depends(get_session),
    service: AuthorizationService = Depends(AuthorizationService),
) -> MembershipResponse:
    """Return one current tenant membership and effective authority."""
    try:
        return await service.get_membership(session, user_id, tenant_id=actor.tenant_id)
    except AuthorizationTargetNotFoundError as error:
        raise HTTPException(status_code=404, detail="Membership not found") from error


@router.patch("/memberships/{user_id}/role", response_model=MembershipResponse)
async def assign_membership_role(
    user_id: int,
    body: RoleAssignmentRequest,
    actor: AuthorizationContext = Depends(get_authorized_auth_context),
    session: AsyncSession = Depends(get_session),
    service: AuthorizationService = Depends(AuthorizationService),
) -> MembershipResponse:
    """Replace one tenant member's application role."""
    try:
        response = await service.assign_role(
            session,
            actor=actor,
            target_user_id=user_id,
            new_role=body.role,
        )
        await session.commit()
        return response
    except AuthorizationTargetNotFoundError as error:
        await session.rollback()
        raise HTTPException(status_code=404, detail="Membership not found") from error
    except (
        AuthorizationPrivilegeEscalationError,
        AuthorizationSelfChangeError,
    ) as error:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authorization change is not permitted",
        ) from error
    except LastTenantAdministratorError as error:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="At least one active tenant administrator is required",
        ) from error


@router.patch("/memberships/{user_id}/status", response_model=MembershipResponse)
async def update_membership_status(
    user_id: int,
    body: MembershipStatusRequest,
    actor: AuthorizationContext = Depends(get_authorized_auth_context),
    session: AsyncSession = Depends(get_session),
    service: AuthorizationService = Depends(AuthorizationService),
) -> MembershipResponse:
    """Enable or revoke one tenant membership."""
    try:
        response = await service.set_membership_active(
            session,
            actor=actor,
            target_user_id=user_id,
            active=body.active,
        )
        await session.commit()
        return response
    except AuthorizationTargetNotFoundError as error:
        await session.rollback()
        raise HTTPException(status_code=404, detail="Membership not found") from error
    except AuthorizationSelfChangeError as error:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authorization change is not permitted",
        ) from error
    except LastTenantAdministratorError as error:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="At least one active tenant administrator is required",
        ) from error
