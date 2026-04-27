from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_role
from app.enums import RoleCode
from app.models.organization import User
from app.schemas.brand import BrandCreate, BrandResponse, BrandUpdate
from app.schemas.common import PaginatedResponse, PaginationParams
from app.services import brand as brand_svc

router = APIRouter()


@router.get("", response_model=PaginatedResponse[BrandResponse])
async def list_brands(
    pagination: PaginationParams = Depends(),
    is_active: Optional[bool] = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await brand_svc.list_brands(db, pagination, user=user, is_active=is_active)


@router.get("/{brand_id}", response_model=BrandResponse)
async def get_brand(
    brand_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await brand_svc.get_brand(db, brand_id, user=user)


@router.post("", response_model=BrandResponse, status_code=201)
async def create_brand(
    data: BrandCreate,
    user: User = Depends(require_role(RoleCode.ADMIN, RoleCode.MANAGER)),
    db: AsyncSession = Depends(get_db),
):
    return await brand_svc.create_brand(db, data, user=user)


@router.patch("/{brand_id}", response_model=BrandResponse)
async def update_brand(
    brand_id: int,
    data: BrandUpdate,
    user: User = Depends(require_role(RoleCode.ADMIN, RoleCode.MANAGER)),
    db: AsyncSession = Depends(get_db),
):
    return await brand_svc.update_brand(db, brand_id, data, user=user)


@router.delete("/{brand_id}", status_code=204)
async def delete_brand(
    brand_id: int,
    user: User = Depends(require_role(RoleCode.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    await brand_svc.delete_brand(db, brand_id, user=user)
