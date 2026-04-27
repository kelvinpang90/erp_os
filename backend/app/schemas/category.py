from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CategoryCreate(BaseModel):
    code: str = Field(max_length=32)
    name: str = Field(max_length=120)
    name_zh: str | None = Field(default=None, max_length=120)
    parent_id: int | None = None


class CategoryUpdate(BaseModel):
    code: str | None = Field(default=None, max_length=32)
    name: str | None = Field(default=None, max_length=120)
    name_zh: str | None = None
    parent_id: int | None = None
    is_active: bool | None = None


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    parent_id: int | None
    code: str
    name: str
    name_zh: str | None
    path: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
