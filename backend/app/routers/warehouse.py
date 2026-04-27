# NOTE: do NOT add "from __future__ import annotations" here — breaks slowapi Body() injection
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_role
from app.enums import RoleCode
from app.models.organization import User
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.warehouse import WarehouseCreate, WarehouseDetail, WarehouseResponse, WarehouseUpdate
from app.services import warehouse as warehouse_service

router = APIRouter()

_ADMIN_ROLES = [RoleCode.ADMIN]


@router.get("", response_model=PaginatedResponse[WarehouseResponse])
async def list_warehouses(
    include_inactive: bool = Query(False),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaginatedResponse[WarehouseResponse]:
    return await warehouse_service.list_warehouses(
        db,
        pagination,
        org_id=user.organization_id,
        include_inactive=include_inactive,
    )


@router.get("/all-active", response_model=list[WarehouseResponse])
async def get_all_active_warehouses(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[WarehouseResponse]:
    return await warehouse_service.get_all_active(db, org_id=user.organization_id)


@router.get("/{warehouse_id}", response_model=WarehouseDetail)
async def get_warehouse(
    warehouse_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WarehouseDetail:
    return await warehouse_service.get_warehouse(
        db, warehouse_id, org_id=user.organization_id
    )


@router.post("", response_model=WarehouseDetail, status_code=status.HTTP_201_CREATED)
async def create_warehouse(
    data: WarehouseCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_ADMIN_ROLES)),
) -> WarehouseDetail:
    return await warehouse_service.create_warehouse(
        db, data, org_id=user.organization_id, user=user
    )


@router.patch("/{warehouse_id}", response_model=WarehouseDetail)
async def update_warehouse(
    warehouse_id: int,
    data: WarehouseUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_ADMIN_ROLES)),
) -> WarehouseDetail:
    return await warehouse_service.update_warehouse(
        db, warehouse_id, data, org_id=user.organization_id, user=user
    )


@router.delete("/{warehouse_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_warehouse(
    warehouse_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_ADMIN_ROLES)),
) -> None:
    await warehouse_service.delete_warehouse(
        db, warehouse_id, org_id=user.organization_id, user=user
    )
