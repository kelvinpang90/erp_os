from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CurrencyCreate(BaseModel):
    code: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    name: str = Field(max_length=64)
    symbol: str = Field(max_length=8)
    decimal_places: int = Field(default=2, ge=0, le=6)
    is_active: bool = True


class CurrencyUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=64)
    symbol: str | None = Field(default=None, max_length=8)
    decimal_places: int | None = Field(default=None, ge=0, le=6)
    is_active: bool | None = None


class CurrencyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    symbol: str
    decimal_places: int
    is_active: bool
    created_at: datetime
