# NOTE: do NOT add "from __future__ import annotations" here — breaks slowapi Body() injection
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_role
from app.enums import RoleCode
from app.models.organization import User
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.supplier import SupplierCreate, SupplierDetail, SupplierResponse, SupplierUpdate
from app.services import supplier as supplier_service

router = APIRouter()

_READ_ROLES = [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.PURCHASER]
_WRITE_ROLES = [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.PURCHASER]
_DELETE_ROLES = [RoleCode.ADMIN, RoleCode.MANAGER]


@router.get("", response_model=PaginatedResponse[SupplierResponse])
async def list_suppliers(
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_READ_ROLES)),
) -> PaginatedResponse[SupplierResponse]:
    return await supplier_service.list_suppliers(
        db,
        pagination,
        org_id=user.organization_id,
        search=search,
        is_active=is_active,
    )


@router.get("/{supplier_id}", response_model=SupplierDetail)
async def get_supplier(
    supplier_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_READ_ROLES)),
) -> SupplierDetail:
    return await supplier_service.get_supplier(
        db, supplier_id, org_id=user.organization_id
    )


@router.post("", response_model=SupplierDetail, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    data: SupplierCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_WRITE_ROLES)),
) -> SupplierDetail:
    return await supplier_service.create_supplier(
        db, data, org_id=user.organization_id, user=user
    )


@router.patch("/{supplier_id}", response_model=SupplierDetail)
async def update_supplier(
    supplier_id: int,
    data: SupplierUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_WRITE_ROLES)),
) -> SupplierDetail:
    return await supplier_service.update_supplier(
        db, supplier_id, data, org_id=user.organization_id, user=user
    )


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_supplier(
    supplier_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_DELETE_ROLES)),
) -> None:
    await supplier_service.delete_supplier(
        db, supplier_id, org_id=user.organization_id, user=user
    )
