"""Pydantic schemas for DeliveryOrder module (Window 10)."""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

_decimal_cfg = ConfigDict(from_attributes=True, json_encoders={Decimal: str})


# ── Line schemas ──────────────────────────────────────────────────────────────


class DeliveryOrderLineCreate(BaseModel):
    """Input schema for a single DO line.

    qty_shipped is required and must be > 0. unit_cost is NOT user-supplied —
    the service captures stock.avg_cost at the moment of shipment and writes
    it to SalesOrderLine.snapshot_avg_cost (first shipment only) for future
    Credit Note rollback.
    """

    sales_order_line_id: int
    qty_shipped: Decimal = Field(..., gt=Decimal("0"))
    batch_no: Optional[str] = Field(None, max_length=64)
    expiry_date: Optional[date] = None
    serial_no: Optional[str] = Field(None, max_length=128)


class DeliveryOrderLineResponse(BaseModel):
    id: int
    line_no: int
    sales_order_line_id: int
    sku_id: int
    sku_code: str = ""
    sku_name: str = ""
    uom_id: int
    qty_shipped: Decimal
    # Snapshot fields from the referenced SO line for convenient display
    qty_ordered: Decimal = Decimal("0")
    qty_already_shipped: Decimal = Decimal("0")
    batch_no: Optional[str]
    expiry_date: Optional[date]
    serial_no: Optional[str]
    created_at: datetime

    model_config = _decimal_cfg


# ── Header schemas ────────────────────────────────────────────────────────────


class DeliveryOrderCreate(BaseModel):
    sales_order_id: int
    delivery_date: date
    shipping_method: Optional[str] = Field(None, max_length=64)
    tracking_no: Optional[str] = Field(None, max_length=64)
    delivered_by: Optional[int] = None
    remarks: Optional[str] = None
    lines: List[DeliveryOrderLineCreate] = Field(..., min_length=1)


class DeliveryOrderResponse(BaseModel):
    id: int
    organization_id: int
    document_no: str
    sales_order_id: int
    sales_order_no: str = ""  # convenience for list view
    warehouse_id: int
    delivery_date: date
    shipping_method: Optional[str]
    tracking_no: Optional[str]
    delivered_by: Optional[int]
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime

    model_config = _decimal_cfg


class DeliveryOrderDetail(DeliveryOrderResponse):
    remarks: Optional[str]
    warehouse_name: str = ""
    delivered_by_name: str = ""
    lines: List[DeliveryOrderLineResponse] = []

    model_config = _decimal_cfg
