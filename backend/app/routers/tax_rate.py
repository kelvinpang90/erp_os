from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_role
from app.enums import RoleCode
from app.models.organization import User
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.tax_rate import TaxRateCreate, TaxRateResponse, TaxRateUpdate
from app.services import tax_rate as tax_rate_svc

router = APIRouter()


@router.get("", response_model=PaginatedResponse[TaxRateResponse])
async def list_tax_rates(
    pagination: PaginationParams = Depends(),
    is_active: Optional[bool] = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await tax_rate_svc.list_tax_rates(db, pagination, user=user, is_active=is_active)


@router.get("/{tax_rate_id}", response_model=TaxRateResponse)
async def get_tax_rate(
    tax_rate_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await tax_rate_svc.get_tax_rate(db, tax_rate_id, user=user)


@router.post("", response_model=TaxRateResponse, status_code=201)
async def create_tax_rate(
    data: TaxRateCreate,
    user: User = Depends(require_role(RoleCode.ADMIN, RoleCode.MANAGER)),
    db: AsyncSession = Depends(get_db),
):
    return await tax_rate_svc.create_tax_rate(db, data, user=user)


@router.patch("/{tax_rate_id}", response_model=TaxRateResponse)
async def update_tax_rate(
    tax_rate_id: int,
    data: TaxRateUpdate,
    user: User = Depends(require_role(RoleCode.ADMIN, RoleCode.MANAGER)),
    db: AsyncSession = Depends(get_db),
):
    return await tax_rate_svc.update_tax_rate(db, tax_rate_id, data, user=user)


@router.delete("/{tax_rate_id}", status_code=204)
async def delete_tax_rate(
    tax_rate_id: int,
    user: User = Depends(require_role(RoleCode.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    await tax_rate_svc.delete_tax_rate(db, tax_rate_id, user=user)
