"""
Authentication-related Pydantic schemas.
"""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr = Field(description="User email address")
    password: str = Field(min_length=1, description="Plaintext password")


class TokenResponse(BaseModel):
    """Returned on successful login or token refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token TTL in seconds")


class RefreshRequest(BaseModel):
    refresh_token: str = Field(description="UUID4 refresh token received at login")


class LogoutRequest(BaseModel):
    refresh_token: str = Field(description="UUID4 refresh token to revoke")
