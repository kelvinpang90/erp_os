"""Read-only Pydantic schemas for Window 14 inventory analytics endpoints.

Branch-inventory matrix (SKU × Warehouse heatmap) and low-stock alerts —
both are aggregated views built on top of `stocks` and `skus`, so they live
here rather than in `stock_movement.py` (which is the audit-trail surface).
"""

from __future__ import annotations

from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


_cfg = ConfigDict(from_attributes=True, json_encoders={Decimal: str})


class WarehouseStockCell(BaseModel):
    """One cell in the branch-inventory heatmap — a (sku, warehouse) snapshot."""

    warehouse_id: int
    warehouse_code: str
    warehouse_name: str
    on_hand: Decimal
    reserved: Decimal
    quality_hold: Decimal
    available: Decimal
    incoming: Decimal
    in_transit: Decimal

    model_config = _cfg


class BranchInventoryRow(BaseModel):
    """One row in the matrix — a single SKU spread across all warehouses."""

    sku_id: int
    sku_code: str
    sku_name: str
    sku_name_zh: Optional[str] = None
    safety_stock: Decimal
    reorder_point: Decimal
    reorder_qty: Decimal
    warehouses: List[WarehouseStockCell]

    model_config = _cfg


class BranchInventoryMatrixResponse(BaseModel):
    """Top-level response — list of warehouses (column headers) + rows."""

    warehouses: List["WarehouseHeader"]
    rows: List[BranchInventoryRow]
    total_skus: int

    model_config = _cfg


class WarehouseHeader(BaseModel):
    """Column header for the heatmap — one per active warehouse."""

    id: int
    code: str
    name: str

    model_config = _cfg


class LowStockAlert(BaseModel):
    """Single low-stock row — `available < safety_stock` for one (sku, warehouse)."""

    sku_id: int
    sku_code: str
    sku_name: str
    sku_name_zh: Optional[str] = None
    warehouse_id: int
    warehouse_code: str
    warehouse_name: str
    available: Decimal
    safety_stock: Decimal
    reorder_point: Decimal
    reorder_qty: Decimal
    shortage: Decimal  # safety_stock - available, always > 0 by definition
    suggested_qty: Decimal  # max(reorder_qty, shortage), what to put on a PO

    model_config = _cfg


class LowStockAlertListResponse(BaseModel):
    items: List[LowStockAlert]
    total: int

    model_config = _cfg


BranchInventoryMatrixResponse.model_rebuild()
