# NOTE: do NOT add "from __future__ import annotations" here — breaks slowapi Body() injection
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_role
from app.enums import RoleCode, StockAdjustmentStatus
from app.models.organization import User
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.stock_adjustment import (
    StockAdjustmentCancel,
    StockAdjustmentCreate,
    StockAdjustmentDetail,
    StockAdjustmentResponse,
    StockAdjustmentUpdate,
)
from app.services import stock_adjustment as adjustment_service

router = APIRouter()

_READ_ROLES = [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.PURCHASER, RoleCode.SALES]
# Drafts can be created by Purchaser; only Manager/Admin can confirm (enforced in service).
_WRITE_ROLES = [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.PURCHASER]
_CONFIRM_ROLES = [RoleCode.ADMIN, RoleCode.MANAGER]
_CANCEL_ROLES = [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.PURCHASER]


@router.get("", response_model=PaginatedResponse[StockAdjustmentResponse])
async def list_stock_adjustments(
    status: Optional[StockAdjustmentStatus] = Query(None),
    warehouse_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_READ_ROLES)),
) -> PaginatedResponse[StockAdjustmentResponse]:
    return await adjustment_service.list_adjustments(
        db,
        pagination,
        org_id=user.organization_id,
        status=status,
        warehouse_id=warehouse_id,
        search=search,
    )


@router.post(
    "",
    response_model=StockAdjustmentDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_stock_adjustment(
    data: StockAdjustmentCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_WRITE_ROLES)),
) -> StockAdjustmentDetail:
    return await adjustment_service.create_adjustment(
        db, data, org_id=user.organization_id, user=user
    )


@router.get("/{adj_id}", response_model=StockAdjustmentDetail)
async def get_stock_adjustment(
    adj_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_READ_ROLES)),
) -> StockAdjustmentDetail:
    return await adjustment_service.get_adjustment(
        db, adj_id, org_id=user.organization_id
    )


@router.patch("/{adj_id}", response_model=StockAdjustmentDetail)
async def update_stock_adjustment(
    adj_id: int,
    data: StockAdjustmentUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_WRITE_ROLES)),
) -> StockAdjustmentDetail:
    return await adjustment_service.update_adjustment(
        db, adj_id, data, org_id=user.organization_id, user=user
    )


@router.post("/{adj_id}/confirm", response_model=StockAdjustmentDetail)
async def confirm_stock_adjustment(
    adj_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_CONFIRM_ROLES)),
) -> StockAdjustmentDetail:
    return await adjustment_service.confirm_adjustment(
        db, adj_id, org_id=user.organization_id, user=user
    )


@router.post("/{adj_id}/cancel", response_model=StockAdjustmentDetail)
async def cancel_stock_adjustment(
    adj_id: int,
    data: StockAdjustmentCancel,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_CANCEL_ROLES)),
) -> StockAdjustmentDetail:
    return await adjustment_service.cancel_adjustment(
        db, adj_id, data, org_id=user.organization_id, user=user
    )
