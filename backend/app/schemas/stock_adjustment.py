"""Pydantic schemas for Stock Adjustment (Window 13)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.enums import StockAdjustmentReason, StockAdjustmentStatus

_decimal_cfg = ConfigDict(from_attributes=True, json_encoders={Decimal: str})


# ── Line schemas ──────────────────────────────────────────────────────────────


class StockAdjustmentLineCreate(BaseModel):
    sku_id: int
    uom_id: int
    qty_before: Decimal = Field(..., ge=Decimal("0"))
    qty_after: Decimal = Field(..., ge=Decimal("0"))
    unit_cost: Optional[Decimal] = Field(None, ge=Decimal("0"))
    batch_no: Optional[str] = Field(None, max_length=64)
    expiry_date: Optional[date] = None
    notes: Optional[str] = Field(None, max_length=500)


class StockAdjustmentLineResponse(BaseModel):
    id: int
    line_no: int
    sku_id: int
    sku_code: str = ""
    sku_name: str = ""
    uom_id: int
    qty_before: Decimal
    qty_after: Decimal
    qty_diff: Optional[Decimal]  # Computed in DB.
    unit_cost: Optional[Decimal]
    batch_no: Optional[str]
    expiry_date: Optional[date]
    notes: Optional[str]

    model_config = _decimal_cfg


# ── Header schemas ────────────────────────────────────────────────────────────


class StockAdjustmentCreate(BaseModel):
    warehouse_id: int
    business_date: date
    reason: StockAdjustmentReason
    reason_description: Optional[str] = Field(None, max_length=500)
    remarks: Optional[str] = Field(None, max_length=500)
    lines: List[StockAdjustmentLineCreate] = Field(..., min_length=1)


class StockAdjustmentUpdate(BaseModel):
    warehouse_id: Optional[int] = None
    business_date: Optional[date] = None
    reason: Optional[StockAdjustmentReason] = None
    reason_description: Optional[str] = Field(None, max_length=500)
    remarks: Optional[str] = Field(None, max_length=500)
    lines: Optional[List[StockAdjustmentLineCreate]] = Field(None, min_length=1)


class StockAdjustmentCancel(BaseModel):
    cancel_reason: str = Field(..., min_length=1, max_length=500)


class StockAdjustmentResponse(BaseModel):
    id: int
    organization_id: int
    document_no: str
    status: StockAdjustmentStatus
    warehouse_id: int
    business_date: date
    reason: StockAdjustmentReason
    approved_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = _decimal_cfg


class StockAdjustmentDetail(StockAdjustmentResponse):
    reason_description: Optional[str]
    remarks: Optional[str]
    approved_by: Optional[int]
    created_by: Optional[int]
    warehouse_name: str = ""
    lines: List[StockAdjustmentLineResponse] = []

    model_config = _decimal_cfg
