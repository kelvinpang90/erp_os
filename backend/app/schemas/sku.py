from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.enums import CostingMethod
from app.schemas.brand import BrandResponse
from app.schemas.category import CategoryResponse
from app.schemas.uom import UOMResponse
from app.schemas.tax_rate import TaxRateResponse


class SKUCreate(BaseModel):
    code: str | None = Field(default=None, max_length=64, description="Leave empty to auto-generate (e.g. SKU-00001)")
    barcode: str | None = Field(default=None, max_length=64)
    name: str = Field(max_length=200)
    name_zh: str | None = Field(default=None, max_length=200)
    description: str | None = None
    brand_id: int | None = None
    category_id: int | None = None
    base_uom_id: int
    tax_rate_id: int
    msic_code: str | None = Field(default=None, max_length=8)
    unit_price_excl_tax: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    unit_price_incl_tax: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    price_tax_inclusive: bool = False
    currency: str = Field(default="MYR", max_length=3)
    costing_method: CostingMethod = CostingMethod.WEIGHTED_AVERAGE
    safety_stock: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    reorder_point: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    reorder_qty: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    track_batch: bool = False
    track_expiry: bool = False
    track_serial: bool = False
    shelf_life_days: int | None = Field(default=None, ge=1)
    image_url: str | None = Field(default=None, max_length=512)
    weight_kg: Decimal | None = Field(default=None, ge=Decimal("0"))


class SKUUpdate(BaseModel):
    barcode: str | None = Field(default=None, max_length=64)
    name: str | None = Field(default=None, max_length=200)
    name_zh: str | None = None
    description: str | None = None
    brand_id: int | None = None
    category_id: int | None = None
    base_uom_id: int | None = None
    tax_rate_id: int | None = None
    msic_code: str | None = Field(default=None, max_length=8)
    unit_price_excl_tax: Decimal | None = Field(default=None, ge=Decimal("0"))
    unit_price_incl_tax: Decimal | None = Field(default=None, ge=Decimal("0"))
    price_tax_inclusive: bool | None = None
    currency: str | None = Field(default=None, max_length=3)
    costing_method: CostingMethod | None = None
    safety_stock: Decimal | None = Field(default=None, ge=Decimal("0"))
    reorder_point: Decimal | None = Field(default=None, ge=Decimal("0"))
    reorder_qty: Decimal | None = Field(default=None, ge=Decimal("0"))
    track_batch: bool | None = None
    track_expiry: bool | None = None
    track_serial: bool | None = None
    shelf_life_days: int | None = Field(default=None, ge=1)
    image_url: str | None = Field(default=None, max_length=512)
    weight_kg: Decimal | None = Field(default=None, ge=Decimal("0"))
    is_active: bool | None = None


class SKUResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    code: str
    barcode: str | None
    name: str
    name_zh: str | None
    description: str | None
    brand_id: int | None
    category_id: int | None
    base_uom_id: int
    tax_rate_id: int
    msic_code: str | None
    unit_price_excl_tax: Decimal
    unit_price_incl_tax: Decimal
    price_tax_inclusive: bool
    currency: str
    costing_method: CostingMethod
    last_cost: Decimal | None
    safety_stock: Decimal
    reorder_point: Decimal
    reorder_qty: Decimal
    track_batch: bool
    track_expiry: bool
    track_serial: bool
    shelf_life_days: int | None
    image_url: str | None
    weight_kg: Decimal | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SKUDetail(SKUResponse):
    brand: BrandResponse | None = None
    category: CategoryResponse | None = None
    base_uom: UOMResponse | None = None
    tax_rate: TaxRateResponse | None = None
