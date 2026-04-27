# NOTE: do NOT add "from __future__ import annotations" here — breaks slowapi Body() injection
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_role
from app.enums import POStatus, RoleCode
from app.models.organization import User
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.purchase_order import (
    PurchaseOrderCancel,
    PurchaseOrderCreate,
    PurchaseOrderDetail,
    PurchaseOrderResponse,
    PurchaseOrderUpdate,
)
from app.services import purchase as purchase_service

router = APIRouter()

_READ_ROLES = [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.PURCHASER]
_WRITE_ROLES = [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.PURCHASER]
_CONFIRM_ROLES = [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.PURCHASER]
# Cancel requires Manager/Admin for CONFIRMED POs (enforced in service layer)
_CANCEL_ROLES = [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.PURCHASER]


@router.get("", response_model=PaginatedResponse[PurchaseOrderResponse])
async def list_purchase_orders(
    status: Optional[POStatus] = Query(None),
    supplier_id: Optional[int] = Query(None),
    warehouse_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_READ_ROLES)),
) -> PaginatedResponse[PurchaseOrderResponse]:
    return await purchase_service.list_pos(
        db,
        pagination,
        org_id=user.organization_id,
        status=status,
        supplier_id=supplier_id,
        warehouse_id=warehouse_id,
        search=search,
    )


@router.post("", response_model=PurchaseOrderDetail, status_code=status.HTTP_201_CREATED)
async def create_purchase_order(
    data: PurchaseOrderCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_WRITE_ROLES)),
) -> PurchaseOrderDetail:
    return await purchase_service.create_po(
        db, data, org_id=user.organization_id, user=user
    )


@router.get("/{po_id}", response_model=PurchaseOrderDetail)
async def get_purchase_order(
    po_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_READ_ROLES)),
) -> PurchaseOrderDetail:
    return await purchase_service.get_po(db, po_id, org_id=user.organization_id)


@router.patch("/{po_id}", response_model=PurchaseOrderDetail)
async def update_purchase_order(
    po_id: int,
    data: PurchaseOrderUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_WRITE_ROLES)),
) -> PurchaseOrderDetail:
    return await purchase_service.update_po(
        db, po_id, data, org_id=user.organization_id, user=user
    )


@router.post("/{po_id}/confirm", response_model=PurchaseOrderDetail)
async def confirm_purchase_order(
    po_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_CONFIRM_ROLES)),
) -> PurchaseOrderDetail:
    return await purchase_service.confirm_po(db, po_id, org_id=user.organization_id, user=user)


@router.post("/{po_id}/cancel", response_model=PurchaseOrderDetail)
async def cancel_purchase_order(
    po_id: int,
    data: PurchaseOrderCancel,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_CANCEL_ROLES)),
) -> PurchaseOrderDetail:
    return await purchase_service.cancel_po(
        db, po_id, data, org_id=user.organization_id, user=user
    )
