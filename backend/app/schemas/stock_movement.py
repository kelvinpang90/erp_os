"""Read-only Pydantic schemas for Stock Movement listing (Window 13)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.enums import StockMovementSourceType, StockMovementType

_decimal_cfg = ConfigDict(from_attributes=True, json_encoders={Decimal: str})


class StockMovementResponse(BaseModel):
    """Single audit row from stock_movements with sku/warehouse names eager-joined."""

    id: int
    organization_id: int
    sku_id: int
    sku_code: str = ""
    sku_name: str = ""
    warehouse_id: int
    warehouse_name: str = ""
    movement_type: StockMovementType
    quantity: Decimal
    unit_cost: Optional[Decimal]
    avg_cost_after: Optional[Decimal]
    source_document_type: StockMovementSourceType
    source_document_id: int
    source_line_id: Optional[int]
    batch_no: Optional[str]
    expiry_date: Optional[date]
    serial_no: Optional[str]
    notes: Optional[str]
    actor_user_id: Optional[int]
    occurred_at: datetime

    model_config = _decimal_cfg
