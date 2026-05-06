"""Admin Users CRUD schemas (separate from /me schemas)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    locale: str
    theme: str
    is_active: bool
    last_login_at: datetime | None = None
    role_codes: list[str] = Field(default_factory=list)


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=128)
    role_codes: list[str] = Field(default_factory=list)
    locale: str = Field(default="en-US")
    theme: str = Field(default="light")


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    role_codes: list[str] | None = None
    locale: str | None = None
    theme: str | None = None
    is_active: bool | None = None


class PasswordReset(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)
