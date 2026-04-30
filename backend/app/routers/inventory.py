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

from app.core.deps import get_db, require_role
from app.enums import RoleCode, StockMovementSourceType, StockMovementType
from app.models.organization import User
from app.models.stock import StockMovement
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.stock_movement import StockMovementResponse

router = APIRouter()

_READ_ROLES = [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.PURCHASER, RoleCode.SALES]


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
