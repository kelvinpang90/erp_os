"""Pydantic schemas for GoodsReceipt module (Window 8)."""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

_decimal_cfg = ConfigDict(from_attributes=True, json_encoders={Decimal: str})


# ── Line schemas ──────────────────────────────────────────────────────────────


class GoodsReceiptLineCreate(BaseModel):
    """Input schema for a single GR line.

    qty_received is required and must be > 0.
    unit_cost is optional — when omitted, the service will default to the
    referenced PO line's unit_price_excl_tax.
    """

    purchase_order_line_id: int
    qty_received: Decimal = Field(..., gt=Decimal("0"))
    unit_cost: Optional[Decimal] = Field(None, ge=Decimal("0"))
    batch_no: Optional[str] = Field(None, max_length=64)
    expiry_date: Optional[date] = None
    remarks: Optional[str] = Field(None, max_length=500)


class GoodsReceiptLineResponse(BaseModel):
    id: int
    line_no: int
    purchase_order_line_id: int
    sku_id: int
    sku_code: str = ""
    sku_name: str = ""
    uom_id: int
    qty_received: Decimal
    unit_cost: Decimal
    # Snapshot fields from the referenced PO line for convenient display
    qty_ordered: Decimal = Decimal("0")
    qty_already_received: Decimal = Decimal("0")
    batch_no: Optional[str]
    expiry_date: Optional[date]
    remarks: Optional[str]
    created_at: datetime

    model_config = _decimal_cfg


# ── Header schemas ────────────────────────────────────────────────────────────


class GoodsReceiptCreate(BaseModel):
    purchase_order_id: int
    receipt_date: date
    delivery_note_no: Optional[str] = Field(None, max_length=64)
    received_by: Optional[int] = None
    remarks: Optional[str] = None
    lines: List[GoodsReceiptLineCreate] = Field(..., min_length=1)


class GoodsReceiptResponse(BaseModel):
    id: int
    organization_id: int
    document_no: str
    purchase_order_id: int
    purchase_order_no: str = ""  # convenience for list view
    warehouse_id: int
    receipt_date: date
    delivery_note_no: Optional[str]
    received_by: Optional[int]
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime

    model_config = _decimal_cfg


class GoodsReceiptDetail(GoodsReceiptResponse):
    remarks: Optional[str]
    # Convenience name fields populated by the service layer (eager-loaded
    # relations) so the UI can show human-readable labels.
    warehouse_name: str = ""
    received_by_name: str = ""
    lines: List[GoodsReceiptLineResponse] = []

    model_config = _decimal_cfg
