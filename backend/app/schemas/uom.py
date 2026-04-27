from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UOMCreate(BaseModel):
    code: str = Field(max_length=16)
    name: str = Field(max_length=64)
    name_zh: str | None = Field(default=None, max_length=64)


class UOMUpdate(BaseModel):
    code: str | None = Field(default=None, max_length=16)
    name: str | None = Field(default=None, max_length=64)
    name_zh: str | None = None
    is_active: bool | None = None


class UOMResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    code: str
    name: str
    name_zh: str | None
    is_active: bool
    created_at: datetime
