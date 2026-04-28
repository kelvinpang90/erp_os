# NOTE: do NOT add "from __future__ import annotations" here — breaks slowapi Body() injection
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_role
from app.enums import RoleCode
from app.models.organization import User
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.goods_receipt import (
    GoodsReceiptCreate,
    GoodsReceiptDetail,
    GoodsReceiptResponse,
)
from app.services import goods_receipt as gr_service

router = APIRouter()

_READ_ROLES = [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.PURCHASER]
_WRITE_ROLES = [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.PURCHASER]


@router.get("", response_model=PaginatedResponse[GoodsReceiptResponse])
async def list_goods_receipts(
    purchase_order_id: Optional[int] = Query(None),
    warehouse_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_READ_ROLES)),
) -> PaginatedResponse[GoodsReceiptResponse]:
    return await gr_service.list_grs(
        db,
        pagination,
        org_id=user.organization_id,
        purchase_order_id=purchase_order_id,
        warehouse_id=warehouse_id,
        search=search,
    )


@router.post("", response_model=GoodsReceiptDetail, status_code=status.HTTP_201_CREATED)
async def create_goods_receipt(
    data: GoodsReceiptCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_WRITE_ROLES)),
) -> GoodsReceiptDetail:
    return await gr_service.create_gr(
        db, data, org_id=user.organization_id, user=user
    )


@router.get("/{gr_id}", response_model=GoodsReceiptDetail)
async def get_goods_receipt(
    gr_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_READ_ROLES)),
) -> GoodsReceiptDetail:
    return await gr_service.get_gr(db, gr_id, org_id=user.organization_id)
