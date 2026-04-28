# NOTE: do NOT add "from __future__ import annotations" here — breaks slowapi Body() injection
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_role
from app.enums import RoleCode
from app.models.organization import User
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.delivery_order import (
    DeliveryOrderCreate,
    DeliveryOrderDetail,
    DeliveryOrderResponse,
)
from app.services import delivery_order as do_service

router = APIRouter()

_READ_ROLES = [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.SALES]
_WRITE_ROLES = [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.SALES]


@router.get("", response_model=PaginatedResponse[DeliveryOrderResponse])
async def list_delivery_orders(
    sales_order_id: Optional[int] = Query(None),
    warehouse_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_READ_ROLES)),
) -> PaginatedResponse[DeliveryOrderResponse]:
    return await do_service.list_dos(
        db,
        pagination,
        org_id=user.organization_id,
        sales_order_id=sales_order_id,
        warehouse_id=warehouse_id,
        search=search,
    )


@router.post("", response_model=DeliveryOrderDetail, status_code=status.HTTP_201_CREATED)
async def create_delivery_order(
    data: DeliveryOrderCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_WRITE_ROLES)),
) -> DeliveryOrderDetail:
    return await do_service.create_do(
        db, data, org_id=user.organization_id, user=user
    )


@router.get("/{do_id}", response_model=DeliveryOrderDetail)
async def get_delivery_order(
    do_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_READ_ROLES)),
) -> DeliveryOrderDetail:
    return await do_service.get_do(db, do_id, org_id=user.organization_id)
