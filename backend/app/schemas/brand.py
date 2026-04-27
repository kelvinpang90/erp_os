from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BrandCreate(BaseModel):
    code: str = Field(max_length=32)
    name: str = Field(max_length=120)
    logo_url: str | None = Field(default=None, max_length=512)


class BrandUpdate(BaseModel):
    code: str | None = Field(default=None, max_length=32)
    name: str | None = Field(default=None, max_length=120)
    logo_url: str | None = None
    is_active: bool | None = None


class BrandResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    code: str
    name: str
    logo_url: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
