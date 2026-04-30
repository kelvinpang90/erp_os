# NOTE: do NOT add "from __future__ import annotations" here — breaks slowapi Body() injection
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_role
from app.enums import RoleCode, StockTransferStatus
from app.models.organization import User
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.stock_transfer import (
    StockTransferCancel,
    StockTransferCreate,
    StockTransferDetail,
    StockTransferReceiveRequest,
    StockTransferResponse,
    StockTransferUpdate,
)
from app.services import stock_transfer as transfer_service

router = APIRouter()

_READ_ROLES = [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.PURCHASER, RoleCode.SALES]
_WRITE_ROLES = [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.PURCHASER]
_CONFIRM_ROLES = [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.PURCHASER]
# Cancel is allowed by Purchaser only when DRAFT; CONFIRMED → enforced in service.
_CANCEL_ROLES = [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.PURCHASER]


@router.get("", response_model=PaginatedResponse[StockTransferResponse])
async def list_stock_transfers(
    status: Optional[StockTransferStatus] = Query(None),
    from_warehouse_id: Optional[int] = Query(None),
    to_warehouse_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_READ_ROLES)),
) -> PaginatedResponse[StockTransferResponse]:
    return await transfer_service.list_transfers(
        db,
        pagination,
        org_id=user.organization_id,
        status=status,
        from_warehouse_id=from_warehouse_id,
        to_warehouse_id=to_warehouse_id,
        search=search,
    )


@router.post(
    "",
    response_model=StockTransferDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_stock_transfer(
    data: StockTransferCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_WRITE_ROLES)),
) -> StockTransferDetail:
    return await transfer_service.create_transfer(
        db, data, org_id=user.organization_id, user=user
    )


@router.get("/{transfer_id}", response_model=StockTransferDetail)
async def get_stock_transfer(
    transfer_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_READ_ROLES)),
) -> StockTransferDetail:
    return await transfer_service.get_transfer(
        db, transfer_id, org_id=user.organization_id
    )


@router.patch("/{transfer_id}", response_model=StockTransferDetail)
async def update_stock_transfer(
    transfer_id: int,
    data: StockTransferUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_WRITE_ROLES)),
) -> StockTransferDetail:
    return await transfer_service.update_transfer(
        db, transfer_id, data, org_id=user.organization_id, user=user
    )


@router.post("/{transfer_id}/confirm", response_model=StockTransferDetail)
async def confirm_stock_transfer(
    transfer_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_CONFIRM_ROLES)),
) -> StockTransferDetail:
    return await transfer_service.confirm_transfer(
        db, transfer_id, org_id=user.organization_id, user=user
    )


@router.post("/{transfer_id}/ship-out", response_model=StockTransferDetail)
async def ship_out_stock_transfer(
    transfer_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_CONFIRM_ROLES)),
) -> StockTransferDetail:
    return await transfer_service.ship_out_transfer(
        db, transfer_id, org_id=user.organization_id, user=user
    )


@router.post("/{transfer_id}/receive", response_model=StockTransferDetail)
async def receive_stock_transfer(
    transfer_id: int,
    data: StockTransferReceiveRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_CONFIRM_ROLES)),
) -> StockTransferDetail:
    return await transfer_service.receive_transfer(
        db, transfer_id, data, org_id=user.organization_id, user=user
    )


@router.post("/{transfer_id}/cancel", response_model=StockTransferDetail)
async def cancel_stock_transfer(
    transfer_id: int,
    data: StockTransferCancel,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_CANCEL_ROLES)),
) -> StockTransferDetail:
    return await transfer_service.cancel_transfer(
        db, transfer_id, data, org_id=user.organization_id, user=user
    )
