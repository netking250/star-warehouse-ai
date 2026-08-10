from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, description="密码")
    tenant_id: str = Field(default="default", min_length=1, max_length=64, description="租户 ID")


class EnterpriseLoginRequest(BaseModel):
    """Exchange a validated enterprise access token for a platform token."""

    access_token: str = Field(min_length=16, max_length=8192)
    tenant_id: str = Field(default="default", min_length=1, max_length=64)


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, description="密码")
    email: EmailStr = Field(..., description="邮箱")
    full_name: str = Field(..., min_length=2, max_length=100, description="真实姓名")
    phone: str | None = Field(default=None, description="手机号")


class TokenResponse(BaseModel):
    access_token: str = Field(description="JWT access token")
    token_type: str = Field(default="bearer", description="OAuth2 token type")
    user_id: int = Field(description="Authenticated user ID")
    username: str = Field(description="Authenticated username")
    full_name: str = Field(description="User display name")
    is_admin: bool = Field(description="Backward-compatible administrator flag")
    tenant_id: str = Field(description="Tenant namespace")
    roles: list[str] = Field(description="Assigned RBAC roles")
    scopes: list[str] = Field(description="Granted authorization scopes")
    session_id: str = Field(description="Authenticated login session ID")


class UserInfoResponse(BaseModel):
    user_id: int
    username: str
    email: str
    full_name: str
    phone: str | None
    is_admin: bool
    created_at: str
    tenant_id: str = Field(description="Tenant namespace")
    roles: list[str] = Field(description="Assigned RBAC roles")
    scopes: list[str] = Field(description="Granted authorization scopes")
    session_id: str = Field(description="Authenticated login session ID")
