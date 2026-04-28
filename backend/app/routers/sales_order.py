# NOTE: do NOT add "from __future__ import annotations" here — breaks slowapi Body() injection
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_role
from app.enums import RoleCode, SOStatus
from app.models.organization import User
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.sales_order import (
    SalesOrderCancel,
    SalesOrderCreate,
    SalesOrderDetail,
    SalesOrderResponse,
    SalesOrderUpdate,
)
from app.services import sales as sales_service

router = APIRouter()

_READ_ROLES = [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.SALES]
_WRITE_ROLES = [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.SALES]
_CONFIRM_ROLES = [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.SALES]
# Cancel requires Manager/Admin for CONFIRMED SOs (enforced in service layer)
_CANCEL_ROLES = [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.SALES]


@router.get("", response_model=PaginatedResponse[SalesOrderResponse])
async def list_sales_orders(
    status: Optional[SOStatus] = Query(None),
    customer_id: Optional[int] = Query(None),
    warehouse_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_READ_ROLES)),
) -> PaginatedResponse[SalesOrderResponse]:
    return await sales_service.list_sos(
        db,
        pagination,
        org_id=user.organization_id,
        status=status,
        customer_id=customer_id,
        warehouse_id=warehouse_id,
        search=search,
    )


@router.post("", response_model=SalesOrderDetail, status_code=status.HTTP_201_CREATED)
async def create_sales_order(
    data: SalesOrderCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_WRITE_ROLES)),
) -> SalesOrderDetail:
    return await sales_service.create_so(
        db, data, org_id=user.organization_id, user=user
    )


@router.get("/{so_id}", response_model=SalesOrderDetail)
async def get_sales_order(
    so_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_READ_ROLES)),
) -> SalesOrderDetail:
    return await sales_service.get_so(db, so_id, org_id=user.organization_id)


@router.patch("/{so_id}", response_model=SalesOrderDetail)
async def update_sales_order(
    so_id: int,
    data: SalesOrderUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_WRITE_ROLES)),
) -> SalesOrderDetail:
    return await sales_service.update_so(
        db, so_id, data, org_id=user.organization_id, user=user
    )


@router.post("/{so_id}/confirm", response_model=SalesOrderDetail)
async def confirm_sales_order(
    so_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_CONFIRM_ROLES)),
) -> SalesOrderDetail:
    return await sales_service.confirm_so(db, so_id, org_id=user.organization_id, user=user)


@router.post("/{so_id}/cancel", response_model=SalesOrderDetail)
async def cancel_sales_order(
    so_id: int,
    data: SalesOrderCancel,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_CANCEL_ROLES)),
) -> SalesOrderDetail:
    return await sales_service.cancel_so(
        db, so_id, data, org_id=user.organization_id, user=user
    )
