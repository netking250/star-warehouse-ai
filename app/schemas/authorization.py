"""API schemas for tenant authorization administration."""

from pydantic import BaseModel, Field

from app.authorization.policy import Role


class MembershipResponse(BaseModel):
    """Current tenant membership and effective application authority."""

    user_id: int = Field(description="Local tenant user identifier")
    username: str = Field(description="Local account username")
    active: bool = Field(description="Whether the tenant membership is active")
    role: Role = Field(description="Current application role")
    scopes: list[str] = Field(description="Current effective canonical capabilities")


class RoleAssignmentRequest(BaseModel):
    """Request to replace a tenant member's single current role."""

    role: Role = Field(description="Application role to assign")


class MembershipStatusRequest(BaseModel):
    """Request to enable or disable a tenant membership."""

    active: bool = Field(description="New tenant membership state")
