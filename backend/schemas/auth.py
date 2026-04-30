"""Auth request/response schemas."""

from pydantic import BaseModel


class UserRegister(BaseModel):
    email: str
    password: str
    role: str = "viewer"  # "admin", "engineer", "viewer"
    engineer_key: str | None = None  # required if role == "engineer"


class UserLogin(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    email: str
    role: str
    team_key: str | None = None
    team_name: str | None = None
    engineer_key: str | None = None
    is_active: bool
