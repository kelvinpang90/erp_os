from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ExchangeRateCreate(BaseModel):
    from_currency: str = Field(min_length=3, max_length=3)
    to_currency: str = Field(min_length=3, max_length=3)
    rate: Decimal = Field(gt=Decimal("0"), decimal_places=8)
    effective_from: date
    effective_to: date | None = None


class ExchangeRateUpdate(BaseModel):
    rate: Decimal | None = Field(default=None, gt=Decimal("0"))
    effective_to: date | None = None


class ExchangeRateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    from_currency: str
    to_currency: str
    rate: Decimal
    effective_from: date
    effective_to: date | None
    source: str
    created_by: int | None
    created_at: datetime
