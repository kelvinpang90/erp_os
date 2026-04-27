# NOTE: do NOT add "from __future__ import annotations" here — breaks slowapi Body() injection
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_role
from app.enums import CustomerType, RoleCode
from app.models.organization import User
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.customer import CustomerCreate, CustomerDetail, CustomerResponse, CustomerUpdate
from app.services import customer as customer_service

router = APIRouter()

_READ_ROLES = [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.SALES]
_WRITE_ROLES = [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.SALES]
_DELETE_ROLES = [RoleCode.ADMIN, RoleCode.MANAGER]


@router.get("", response_model=PaginatedResponse[CustomerResponse])
async def list_customers(
    search: Optional[str] = Query(None),
    customer_type: Optional[CustomerType] = Query(None),
    is_active: Optional[bool] = Query(None),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_READ_ROLES)),
) -> PaginatedResponse[CustomerResponse]:
    return await customer_service.list_customers(
        db,
        pagination,
        org_id=user.organization_id,
        search=search,
        customer_type=customer_type,
        is_active=is_active,
    )


@router.get("/{customer_id}", response_model=CustomerDetail)
async def get_customer(
    customer_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_READ_ROLES)),
) -> CustomerDetail:
    return await customer_service.get_customer(
        db, customer_id, org_id=user.organization_id
    )


@router.post("", response_model=CustomerDetail, status_code=status.HTTP_201_CREATED)
async def create_customer(
    data: CustomerCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_WRITE_ROLES)),
) -> CustomerDetail:
    return await customer_service.create_customer(
        db, data, org_id=user.organization_id, user=user
    )


@router.patch("/{customer_id}", response_model=CustomerDetail)
async def update_customer(
    customer_id: int,
    data: CustomerUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_WRITE_ROLES)),
) -> CustomerDetail:
    return await customer_service.update_customer(
        db, customer_id, data, org_id=user.organization_id, user=user
    )


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(
    customer_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_DELETE_ROLES)),
) -> None:
    await customer_service.delete_customer(
        db, customer_id, org_id=user.organization_id, user=user
    )
