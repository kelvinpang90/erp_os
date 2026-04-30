"""Pydantic schemas for Stock Transfer (Window 13)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.enums import StockTransferStatus

_decimal_cfg = ConfigDict(from_attributes=True, json_encoders={Decimal: str})


# ── Line schemas ──────────────────────────────────────────────────────────────


class StockTransferLineCreate(BaseModel):
    sku_id: int
    uom_id: int
    qty_sent: Decimal = Field(..., gt=Decimal("0"))
    batch_no: Optional[str] = Field(None, max_length=64)
    expiry_date: Optional[date] = None


class StockTransferLineResponse(BaseModel):
    id: int
    line_no: int
    sku_id: int
    sku_code: str = ""
    sku_name: str = ""
    uom_id: int
    qty_sent: Decimal
    qty_received: Decimal
    unit_cost_snapshot: Optional[Decimal]
    batch_no: Optional[str]
    expiry_date: Optional[date]

    model_config = _decimal_cfg


# ── Header schemas ────────────────────────────────────────────────────────────


class StockTransferCreate(BaseModel):
    from_warehouse_id: int
    to_warehouse_id: int
    business_date: date
    expected_arrival_date: Optional[date] = None
    remarks: Optional[str] = Field(None, max_length=500)
    lines: List[StockTransferLineCreate] = Field(..., min_length=1)


class StockTransferUpdate(BaseModel):
    from_warehouse_id: Optional[int] = None
    to_warehouse_id: Optional[int] = None
    business_date: Optional[date] = None
    expected_arrival_date: Optional[date] = None
    remarks: Optional[str] = Field(None, max_length=500)
    lines: Optional[List[StockTransferLineCreate]] = Field(None, min_length=1)


class StockTransferCancel(BaseModel):
    cancel_reason: str = Field(..., min_length=1, max_length=500)


class StockTransferReceiveLine(BaseModel):
    """One line's receive payload — accumulates onto line.qty_received."""

    line_id: int
    qty_received: Decimal = Field(..., gt=Decimal("0"))


class StockTransferReceiveRequest(BaseModel):
    lines: List[StockTransferReceiveLine] = Field(..., min_length=1)


class StockTransferResponse(BaseModel):
    id: int
    organization_id: int
    document_no: str
    status: StockTransferStatus
    from_warehouse_id: int
    to_warehouse_id: int
    business_date: date
    expected_arrival_date: Optional[date]
    actual_arrival_date: Optional[date]
    created_at: datetime
    updated_at: datetime

    model_config = _decimal_cfg


class StockTransferDetail(StockTransferResponse):
    remarks: Optional[str]
    created_by: Optional[int]
    updated_by: Optional[int]
    # Convenience name fields populated from eager-loaded relations.
    from_warehouse_name: str = ""
    to_warehouse_name: str = ""
    lines: List[StockTransferLineResponse] = []

    model_config = _decimal_cfg
