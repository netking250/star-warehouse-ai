# app/services/auth_service.py
"""Authentication business logic service."""

import asyncio
import logging

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.user import User

logger = logging.getLogger(__name__)


class AuthService:
    """Service layer for authentication operations."""

    async def authenticate_user(
        self,
        session: AsyncSession,
        username: str,
        password: str,
        tenant_id: str,
    ) -> User:
        """
        Query user by username and verify credentials.

        Raises:
            HTTPException: 401 if user not found or password wrong, 403 if inactive.
        """
        result = await session.exec(
            select(User).where(User.username == username, User.tenant_id == tenant_id)
        )
        user = result.first()

        if not user:
            logger.info(
                "local_login_failure",
                extra={"event": "local_login_failure", "result": "invalid_credentials"},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            logger.info(
                "local_login_failure",
                extra={
                    "event": "local_login_failure",
                    "user_id": user.id,
                    "result": "user_inactive",
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="账号已被禁用，请联系管理员",
            )

        is_valid = await asyncio.to_thread(user.verify_password, password)
        if not is_valid:
            logger.info(
                "local_login_failure",
                extra={
                    "event": "local_login_failure",
                    "user_id": user.id,
                    "result": "invalid_credentials",
                },
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
                headers={"WWW-Authenticate": "Bearer"},
            )

        logger.info(
            "local_login_success",
            extra={"event": "local_login_success", "user_id": user.id, "result": "success"},
        )
        return user

    async def register_user(
        self,
        session: AsyncSession,
        username: str,
        password: str,
        email: str,
        full_name: str,
        phone: str | None = None,
    ) -> User:
        """
        Create a new user after checking for duplicates.

        Raises:
            HTTPException: 400 if username or email already exists.
        """

        async def _do_register() -> User:
            result = await session.exec(select(User).where(User.username == username))
            if result.first():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="用户名已存在",
                )

            result = await session.exec(select(User).where(User.email == email))
            if result.first():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="邮箱已被注册",
                )

            password_hash = await asyncio.to_thread(User.hash_password, password)
            user = User(
                username=username,
                password_hash=password_hash,
                email=email,
                full_name=full_name,
                phone=phone,
                is_admin=False,
                is_active=True,
            )

            session.add(user)
            return user

        try:
            user = await _do_register()
            await session.flush()
        except IntegrityError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名或邮箱已被注册",
            ) from exc

        await session.refresh(user)
        return user

    async def get_user_info(self, session: AsyncSession, user_id: int) -> User:
        """
        Fetch user information by ID.

        Raises:
            HTTPException: 404 if user not found.
        """
        user = await session.get(User, user_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在",
            )

        return user
