from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.enums import SOStatus

_decimal_cfg = ConfigDict(from_attributes=True, json_encoders={Decimal: str})


# ── Line schemas ──────────────────────────────────────────────────────────────

class SOLineCreate(BaseModel):
    sku_id: int
    uom_id: int
    description: Optional[str] = Field(None, max_length=500)
    qty_ordered: Decimal = Field(..., gt=Decimal("0"))
    unit_price_excl_tax: Decimal = Field(..., ge=Decimal("0"))
    tax_rate_id: int
    # Server-authoritative: real rate is loaded from tax_rates by tax_rate_id;
    # this field is accepted for client-side real-time totals UI but IGNORED
    # by the service layer to prevent percent / id drift.
    tax_rate_percent: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    discount_percent: Decimal = Field(Decimal("0"), ge=Decimal("0"), le=Decimal("100"))
    batch_no: Optional[str] = Field(None, max_length=64)
    expiry_date: Optional[date] = None
    serial_no: Optional[str] = Field(None, max_length=128)


class SOLineResponse(BaseModel):
    id: int
    line_no: int
    sku_id: int
    sku_code: str = ""
    sku_name: str = ""
    uom_id: int
    description: Optional[str]
    qty_ordered: Decimal
    qty_shipped: Decimal
    qty_invoiced: Decimal
    unit_price_excl_tax: Decimal
    tax_rate_id: int
    tax_rate_percent: Decimal
    tax_amount: Decimal
    discount_percent: Decimal
    discount_amount: Decimal
    line_total_excl_tax: Decimal
    line_total_incl_tax: Decimal
    snapshot_avg_cost: Optional[Decimal]
    batch_no: Optional[str]
    expiry_date: Optional[date]
    serial_no: Optional[str]

    model_config = _decimal_cfg


# ── Header schemas ────────────────────────────────────────────────────────────

class SalesOrderCreate(BaseModel):
    customer_id: int
    warehouse_id: int
    business_date: date
    expected_ship_date: Optional[date] = None
    currency: str = Field("MYR", max_length=3)
    exchange_rate: Decimal = Field(Decimal("1"), gt=Decimal("0"))
    payment_terms_days: int = Field(30, ge=0)
    shipping_address: Optional[str] = Field(None, max_length=500)
    shipping_amount: Decimal = Field(Decimal("0"), ge=Decimal("0"))
    remarks: Optional[str] = None
    lines: List[SOLineCreate] = Field(..., min_length=1)


class SalesOrderUpdate(BaseModel):
    customer_id: Optional[int] = None
    warehouse_id: Optional[int] = None
    business_date: Optional[date] = None
    expected_ship_date: Optional[date] = None
    currency: Optional[str] = Field(None, max_length=3)
    exchange_rate: Optional[Decimal] = Field(None, gt=Decimal("0"))
    payment_terms_days: Optional[int] = Field(None, ge=0)
    shipping_address: Optional[str] = Field(None, max_length=500)
    shipping_amount: Optional[Decimal] = Field(None, ge=Decimal("0"))
    remarks: Optional[str] = None
    lines: Optional[List[SOLineCreate]] = Field(None, min_length=1)


class SalesOrderCancel(BaseModel):
    cancel_reason: str = Field(..., min_length=1, max_length=500)


class SalesOrderResponse(BaseModel):
    id: int
    organization_id: int
    document_no: str
    status: SOStatus
    customer_id: int
    warehouse_id: int
    business_date: date
    expected_ship_date: Optional[date]
    currency: str
    exchange_rate: Decimal
    subtotal_excl_tax: Decimal
    tax_amount: Decimal
    discount_amount: Decimal
    shipping_amount: Decimal
    total_incl_tax: Decimal
    payment_terms_days: int
    created_at: datetime
    updated_at: datetime

    model_config = _decimal_cfg


class SalesOrderDetail(SalesOrderResponse):
    base_currency_amount: Decimal
    shipping_address: Optional[str]
    remarks: Optional[str]
    cancel_reason: Optional[str]
    confirmed_at: Optional[datetime]
    fully_shipped_at: Optional[datetime]
    cancelled_at: Optional[datetime]
    created_by: Optional[int]
    updated_by: Optional[int]
    # Convenience name fields populated by the service layer (eager-loaded
    # relations) so the UI can display human-readable labels without an
    # extra round trip to /customers/:id and /warehouses/:id.
    customer_name: str = ""
    warehouse_name: str = ""
    lines: List[SOLineResponse] = []

    model_config = _decimal_cfg
