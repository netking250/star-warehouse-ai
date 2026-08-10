# app/api/v1/auth.py
"""
认证 API - 登录、注册
"""

from uuid import uuid4

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_session
from app.core.limiter import limiter
from app.core.redis import get_redis_client
from app.core.security import (
    AuthContext,
    Role,
    create_access_token,
    get_active_auth_context,
    revoke_auth_context,
    scopes_for_roles,
)
from app.core.tenancy import tenant_scope
from app.models.user import User
from app.schemas.auth import (
    EnterpriseLoginRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserInfoResponse,
)
from app.services.auth_service import AuthService
from app.services.identity_provider import (
    IdentityProvider,
    IdentityProviderError,
    get_identity_provider,
)

router = APIRouter()


def _issue_user_token(user: User) -> tuple[str, str, frozenset[Role], frozenset[str]]:
    if user.id is None:
        raise HTTPException(status_code=500, detail="用户 ID 缺失，请联系管理员")
    role = Role.SUPER_ADMIN if user.is_admin else Role(user.role)
    roles = frozenset({role})
    scopes = scopes_for_roles(roles)
    session_id = str(uuid4())
    token = create_access_token(
        user.id,
        is_admin=user.is_admin,
        tenant_id=user.tenant_id,
        roles=roles,
        scopes=scopes,
        session_id=session_id,
    )
    return token, session_id, roles, scopes


def _token_response(
    user: User,
    token: str,
    session_id: str,
    roles: frozenset[Role],
    scopes: frozenset[str],
) -> TokenResponse:
    if user.id is None:
        raise HTTPException(status_code=500, detail="用户 ID 缺失，请联系管理员")
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
        is_admin=user.is_admin,
        tenant_id=user.tenant_id,
        roles=sorted(role.value for role in roles),
        scopes=sorted(scopes),
        session_id=session_id,
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    response: Response,
    body: LoginRequest,
    session: AsyncSession = Depends(get_session),
    service: AuthService = Depends(AuthService),
):
    """用户登录 - 验证用户名和密码，返回 JWT Token"""
    with tenant_scope(body.tenant_id):
        user = await service.authenticate_user(
            session, body.username, body.password, tenant_id=body.tenant_id
        )
        token, session_id, roles, scopes = _issue_user_token(user)
    return _token_response(user, token, session_id, roles, scopes)


@router.post("/enterprise/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def enterprise_login(
    request: Request,
    response: Response,
    body: EnterpriseLoginRequest,
    session: AsyncSession = Depends(get_session),
    provider: IdentityProvider = Depends(get_identity_provider),
) -> TokenResponse:
    """Exchange an enterprise OIDC identity for a local platform token."""
    try:
        identity = await provider.authenticate(body.access_token)
    except IdentityProviderError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
    with tenant_scope(body.tenant_id):
        result = await session.exec(select(User).where(User.email == str(identity.email)))
        user = result.one_or_none()
        if user is None or not user.is_active:
            raise HTTPException(status_code=403, detail="企业账号未绑定或已被禁用")
        token, session_id, roles, scopes = _issue_user_token(user)
    return _token_response(user, token, session_id, roles, scopes)


@router.post("/register", response_model=TokenResponse)
@limiter.limit("5/minute")
async def register(
    request: Request,
    response: Response,
    body: RegisterRequest,
    session: AsyncSession = Depends(get_session),
    service: AuthService = Depends(AuthService),
):
    user = await service.register_user(
        session,
        username=body.username,
        password=body.password,
        email=body.email,
        full_name=body.full_name,
        phone=body.phone,
    )
    token, session_id, roles, scopes = _issue_user_token(user)
    return _token_response(user, token, session_id, roles, scopes)


@router.get("/me", response_model=UserInfoResponse)
async def get_current_user_info(
    auth_context: AuthContext = Depends(get_active_auth_context),
    session: AsyncSession = Depends(get_session),
    service: AuthService = Depends(AuthService),
):
    """获取当前登录用户信息"""
    user = await service.get_user_info(session, auth_context.user_id)
    if user.id is None:
        raise HTTPException(status_code=500, detail="用户 ID 缺失，请联系管理员")
    return UserInfoResponse(
        user_id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        is_admin=user.is_admin,
        created_at=user.created_at.isoformat(),
        tenant_id=auth_context.tenant_id,
        roles=sorted(role.value for role in auth_context.roles),
        scopes=sorted(auth_context.scopes),
        session_id=auth_context.session_id,
    )


@router.post("/logout", status_code=204)
async def logout(
    auth_context: AuthContext = Depends(get_active_auth_context),
    redis: aioredis.Redis = Depends(get_redis_client),
) -> Response:
    """Immediately revoke the current access token."""
    await revoke_auth_context(auth_context, redis)
    return Response(status_code=204)
