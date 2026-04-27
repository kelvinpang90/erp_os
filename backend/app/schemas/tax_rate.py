from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.enums import TaxType


class TaxRateCreate(BaseModel):
    code: str = Field(max_length=16)
    name: str = Field(max_length=80)
    rate: Decimal = Field(ge=Decimal("0"), le=Decimal("100"), decimal_places=2)
    tax_type: TaxType
    is_default: bool = False


class TaxRateUpdate(BaseModel):
    code: str | None = Field(default=None, max_length=16)
    name: str | None = Field(default=None, max_length=80)
    rate: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("100"))
    tax_type: TaxType | None = None
    is_default: bool | None = None
    is_active: bool | None = None


class TaxRateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    code: str
    name: str
    rate: Decimal
    tax_type: TaxType
    is_default: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
