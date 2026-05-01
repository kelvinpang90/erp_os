# NOTE: do NOT add "from __future__ import annotations" here — breaks slowapi Body() injection
"""Inventory router — read-only views of stock movements (Window 13).

Future windows extend with branch-inventory matrix (W14) and audit trail (W17).
"""

from datetime import date as date_type
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from decimal import Decimal

from app.core.deps import get_db, require_role
from app.enums import RoleCode, StockMovementSourceType, StockMovementType
from app.models.organization import User
from app.models.stock import Stock, StockMovement
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.inventory import (
    BranchInventoryMatrixResponse,
    LowStockAlertListResponse,
)
from app.schemas.stock_movement import StockMovementResponse, StockSnapshotResponse
from app.services import inventory as inventory_service

router = APIRouter()

_READ_ROLES = [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.PURCHASER, RoleCode.SALES]
_RESTOCK_ROLES = [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.PURCHASER]


def _to_response(movement: StockMovement) -> StockMovementResponse:
    resp = StockMovementResponse.model_validate(movement)
    resp.sku_code = movement.sku.code if movement.sku else ""
    resp.sku_name = movement.sku.name if movement.sku else ""
    resp.warehouse_name = movement.warehouse.name if movement.warehouse else ""
    return resp


@router.get(
    "/movements",
    response_model=PaginatedResponse[StockMovementResponse],
)
async def list_stock_movements(
    movement_type: Optional[StockMovementType] = Query(None),
    source_document_type: Optional[StockMovementSourceType] = Query(None),
    sku_id: Optional[int] = Query(None),
    warehouse_id: Optional[int] = Query(None),
    date_from: Optional[date_type] = Query(None),
    date_to: Optional[date_type] = Query(None),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_READ_ROLES)),
) -> PaginatedResponse[StockMovementResponse]:
    """Paginated stock-movement audit trail.

    All filters are AND-combined; missing filters mean "no constraint".
    """
    filters = [StockMovement.organization_id == user.organization_id]
    if movement_type is not None:
        filters.append(StockMovement.movement_type == movement_type)
    if source_document_type is not None:
        filters.append(StockMovement.source_document_type == source_document_type)
    if sku_id is not None:
        filters.append(StockMovement.sku_id == sku_id)
    if warehouse_id is not None:
        filters.append(StockMovement.warehouse_id == warehouse_id)
    if date_from is not None:
        filters.append(StockMovement.occurred_at >= date_from)
    if date_to is not None:
        # date_to is inclusive — extend to end of day on the SQL side by using
        # < (date_to + 1) semantics via simple LE on the date cast.
        filters.append(func.date(StockMovement.occurred_at) <= date_to)

    where_clause = and_(*filters)
    count_stmt = select(func.count()).select_from(StockMovement).where(where_clause)
    stmt = (
        select(StockMovement)
        .where(where_clause)
        .options(
            selectinload(StockMovement.sku),
            selectinload(StockMovement.warehouse),
        )
        .order_by(StockMovement.occurred_at.desc(), StockMovement.id.desc())
        .limit(pagination.page_size)
        .offset(pagination.offset)
    )

    total = (await db.execute(count_stmt)).scalar_one()
    items = list((await db.execute(stmt)).scalars().all())

    return PaginatedResponse[StockMovementResponse].build(
        items=[_to_response(m) for m in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/stocks", response_model=StockSnapshotResponse)
async def get_stock_snapshot(
    sku_id: int = Query(..., description="SKU id"),
    warehouse_id: int = Query(..., description="Warehouse id"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_READ_ROLES)),
) -> StockSnapshotResponse:
    """Current 6-axis stock for one (sku, warehouse) pair.

    The Stock Adjustment create page calls this when the user picks a SKU so
    it can pre-fill `qty_before` (the on-hand book value) — preventing typos
    from polluting the physical-count vs. book-value diff.

    No row in the stocks table is treated as zero across the board, NOT 404,
    so a brand-new SKU/warehouse combination still renders cleanly in the UI.
    """
    stmt = select(Stock).where(
        Stock.organization_id == user.organization_id,
        Stock.sku_id == sku_id,
        Stock.warehouse_id == warehouse_id,
    )
    stock = (await db.execute(stmt)).scalar_one_or_none()
    if stock is None:
        zero = Decimal("0")
        return StockSnapshotResponse(
            sku_id=sku_id,
            warehouse_id=warehouse_id,
            on_hand=zero,
            reserved=zero,
            quality_hold=zero,
            available=zero,
            incoming=zero,
            in_transit=zero,
            avg_cost=zero,
            last_cost=None,
        )
    return StockSnapshotResponse.model_validate(stock)


@router.get("/branch-matrix", response_model=BranchInventoryMatrixResponse)
async def get_branch_inventory_matrix(
    sku_query: Optional[str] = Query(None, description="SKU code/name substring"),
    warehouse_id: Optional[list[int]] = Query(None, description="Filter to specific warehouses"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_RESTOCK_ROLES)),
) -> BranchInventoryMatrixResponse:
    """SKU × Warehouse stock matrix for the heatmap UI.

    Sales role is excluded — branch-level stock visibility is reserved for
    operations / purchasing. Pagination is by SKU rows; warehouses are
    always returned in full so the column header set stays stable across pages.
    """
    return await inventory_service.get_branch_inventory_matrix(
        db,
        organization_id=user.organization_id,
        sku_query=sku_query,
        warehouse_ids=warehouse_id,
        limit=page_size,
        offset=(page - 1) * page_size,
    )


@router.get("/alerts/low-stock", response_model=LowStockAlertListResponse)
async def list_low_stock_alerts(
    warehouse_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_RESTOCK_ROLES)),
) -> LowStockAlertListResponse:
    """List every (sku, warehouse) where available < safety_stock.

    The Alert page consumes this; the bell-badge polls a derived count from
    the notifications table (notify_on_low_stock handler emits one). This
    endpoint is the source of truth for the page itself.
    """
    items = await inventory_service.get_low_stock_alerts(
        db,
        organization_id=user.organization_id,
        warehouse_id=warehouse_id,
    )
    return LowStockAlertListResponse(items=items, total=len(items))
