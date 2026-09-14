"""Authentication API for local credentials and OIDC identities."""

import logging
from uuid import uuid4

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.browser_session import (
    clear_browser_auth_cookie,
    issue_csrf_token,
    set_browser_auth_cookie,
)
from app.core.config import settings
from app.core.database import get_session
from app.core.limiter import limiter
from app.core.redis import get_redis_client
from app.core.security import (
    AuthContext,
    Role,
    create_access_token,
    get_active_auth_context,
    get_auth_context,
    revoke_auth_context,
    scopes_for_roles,
)
from app.core.tenancy import tenant_scope
from app.core.tenant_resolver import TenantResolver, tenant_id_from_request
from app.models.user import User
from app.schemas.auth import (
    BrowserLoginResponse,
    CsrfTokenResponse,
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
from app.services.identity_service import IdentityAuthenticationError, IdentityService

router = APIRouter()
logger = logging.getLogger(__name__)


async def _revoke_replaced_browser_credential(
    request: Request,
    redis: aioredis.Redis,
) -> None:
    """Revoke a valid pre-existing browser credential before session rotation."""
    existing_token = request.cookies.get(settings.BROWSER_AUTH_COOKIE_NAME)
    if existing_token is None:
        return
    try:
        existing_principal = get_auth_context(existing_token)
    except HTTPException:
        return
    await revoke_auth_context(existing_principal, redis)


def get_oidc_provider_dependency() -> IdentityProvider:
    """Map missing OIDC configuration to a stable transport error."""
    try:
        return get_identity_provider()
    except IdentityProviderError as error:
        logger.info(
            "oidc_login_failure",
            extra={"event": "oidc_login_failure", "result": error.code},
        )
        raise HTTPException(
            status_code=503,
            detail="Enterprise identity authentication is unavailable",
        ) from error


def _issue_user_token(user: User) -> tuple[str, str, frozenset[Role], frozenset[str]]:
    if user.id is None:
        raise HTTPException(status_code=500, detail="Authenticated user ID is missing")
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
        raise HTTPException(status_code=500, detail="Authenticated user ID is missing")
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


def _browser_login_response(
    user: User,
    session_id: str,
    roles: frozenset[Role],
    scopes: frozenset[str],
) -> BrowserLoginResponse:
    """Build browser identity state without returning the authentication credential."""
    if user.id is None:
        raise HTTPException(status_code=500, detail="Authenticated user ID is missing")
    return BrowserLoginResponse(
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
    identity_service: IdentityService = Depends(IdentityService),
) -> TokenResponse:
    """Authenticate a local password and return the existing application token."""
    tenant_id = tenant_id_from_request(body.tenant_id)
    tenant_context = await TenantResolver(session).resolve(tenant_id)
    with tenant_scope(tenant_context):
        user = await service.authenticate_user(
            session, body.username, body.password, tenant_id=tenant_id
        )
        identity_result = await identity_service.authenticate_local(user)
        token, session_id, roles, scopes = _issue_user_token(identity_result.user)
    return _token_response(identity_result.user, token, session_id, roles, scopes)


@router.post("/browser/login", response_model=BrowserLoginResponse)
@limiter.limit("5/minute")
async def browser_login(
    request: Request,
    response: Response,
    body: LoginRequest,
    session: AsyncSession = Depends(get_session),
    redis: aioredis.Redis = Depends(get_redis_client),
    service: AuthService = Depends(AuthService),
    identity_service: IdentityService = Depends(IdentityService),
) -> BrowserLoginResponse:
    """Authenticate local credentials and establish an HttpOnly browser session."""
    tenant_id = tenant_id_from_request(body.tenant_id)
    tenant_context = await TenantResolver(session).resolve(tenant_id)
    with tenant_scope(tenant_context):
        user = await service.authenticate_user(
            session, body.username, body.password, tenant_id=tenant_id
        )
        identity_result = await identity_service.authenticate_local(user)
        token, session_id, roles, scopes = _issue_user_token(identity_result.user)
    await _revoke_replaced_browser_credential(request, redis)
    principal = get_auth_context(token)
    set_browser_auth_cookie(response, token, expires_at=principal.expires_at)
    return _browser_login_response(identity_result.user, session_id, roles, scopes)


@router.get("/oidc/login", response_class=RedirectResponse)
@limiter.limit("10/minute")
async def oidc_login(
    request: Request,
    response: Response,
    tenant_id: str = Query(min_length=1, max_length=64),
    session: AsyncSession = Depends(get_session),
    redis: aioredis.Redis = Depends(get_redis_client),
    provider: IdentityProvider = Depends(get_oidc_provider_dependency),
) -> RedirectResponse:
    """Begin OIDC authorization code flow with server-side state, nonce, and PKCE."""
    try:
        tenant_context = await TenantResolver(session).resolve(tenant_id_from_request(tenant_id))
        with tenant_scope(tenant_context):
            authorization_url = await provider.start_authorization(redis, tenant_context.tenant_id)
    except IdentityProviderError as error:
        logger.info(
            "oidc_login_failure",
            extra={"event": "oidc_login_failure", "result": error.code},
        )
        raise HTTPException(
            status_code=503,
            detail="Enterprise identity authentication is unavailable",
        ) from error
    return RedirectResponse(authorization_url, status_code=307)


@router.get("/oidc/callback", response_class=RedirectResponse)
@limiter.limit("10/minute")
async def oidc_callback(
    request: Request,
    state: str = Query(min_length=16, max_length=512),
    code: str = Query(min_length=1, max_length=4096),
    session: AsyncSession = Depends(get_session),
    redis: aioredis.Redis = Depends(get_redis_client),
    provider: IdentityProvider = Depends(get_oidc_provider_dependency),
    identity_service: IdentityService = Depends(IdentityService),
) -> RedirectResponse:
    """Resolve OIDC identity into a fresh HttpOnly application browser session."""
    try:
        identity, tenant_id = await provider.authenticate_callback(redis, state=state, code=code)
        async with session.begin():
            tenant_context = await TenantResolver(session).resolve(tenant_id)
            with tenant_scope(tenant_context):
                result = await identity_service.authenticate_oidc(
                    session,
                    identity,
                    tenant_id=tenant_context.tenant_id,
                )
                token, _, _, _ = _issue_user_token(result.user)
        await _revoke_replaced_browser_credential(request, redis)
        principal = get_auth_context(token)
        redirect = RedirectResponse(
            settings.BROWSER_POST_LOGIN_REDIRECT_PATH,
            status_code=303,
        )
        set_browser_auth_cookie(redirect, token, expires_at=principal.expires_at)
        return redirect
    except (IdentityProviderError, IdentityAuthenticationError) as error:
        logger.info(
            "oidc_login_failure",
            extra={"event": "oidc_login_failure", "result": error.code},
        )
        raise HTTPException(
            status_code=401,
            detail="Enterprise identity authentication failed",
        ) from error


@router.post("/register", response_model=TokenResponse)
@limiter.limit("5/minute")
async def register(
    request: Request,
    response: Response,
    body: RegisterRequest,
    session: AsyncSession = Depends(get_session),
    service: AuthService = Depends(AuthService),
) -> TokenResponse:
    """Register a local user inside the caller-owned transaction."""
    async with session.begin():
        tenant_id = tenant_id_from_request(body.tenant_id)
        tenant_context = await TenantResolver(session).resolve(tenant_id)
        with tenant_scope(tenant_context):
            user = await service.register_user(
                session,
                username=body.username,
                password=body.password,
                email=body.email,
                full_name=body.full_name,
                phone=body.phone,
            )
            token, session_id, roles, scopes = _issue_user_token(user)
            result = _token_response(user, token, session_id, roles, scopes)
    return result


@router.get("/me", response_model=UserInfoResponse)
async def get_current_user_info(
    auth_context: AuthContext = Depends(get_active_auth_context),
    session: AsyncSession = Depends(get_session),
    service: AuthService = Depends(AuthService),
) -> UserInfoResponse:
    """Return the currently authenticated local user's information."""
    user = await service.get_user_info(session, auth_context.user_id)
    if user.id is None:
        raise HTTPException(status_code=500, detail="Authenticated user ID is missing")
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


@router.get("/browser/csrf", response_model=CsrfTokenResponse)
async def get_browser_csrf_token(
    auth_context: AuthContext = Depends(get_active_auth_context),
) -> CsrfTokenResponse:
    """Return a CSRF token bound to the current browser authentication session."""
    return CsrfTokenResponse(csrf_token=issue_csrf_token(auth_context))


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    auth_context: AuthContext = Depends(get_active_auth_context),
    redis: aioredis.Redis = Depends(get_redis_client),
) -> Response:
    """Immediately revoke the current token and clear browser credential transport."""
    await revoke_auth_context(auth_context, redis)
    clear_browser_auth_cookie(response)
    response.status_code = 204
    return response
