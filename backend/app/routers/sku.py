from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_role
from app.enums import RoleCode
from app.models.organization import User
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.sku import SKUCreate, SKUDetail, SKUResponse, SKUUpdate
from app.services import sku as sku_svc

router = APIRouter()


@router.get("", response_model=PaginatedResponse[SKUResponse])
async def list_skus(
    pagination: PaginationParams = Depends(),
    brand_id: Optional[int] = Query(default=None),
    category_id: Optional[int] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    search: Optional[str] = Query(default=None, max_length=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await sku_svc.list_skus(
        db,
        pagination,
        user=user,
        brand_id=brand_id,
        category_id=category_id,
        is_active=is_active,
        search=search,
    )


@router.get("/{sku_id}", response_model=SKUDetail)
async def get_sku(
    sku_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await sku_svc.get_sku(db, sku_id, user=user)


@router.post("", response_model=SKUDetail, status_code=201)
async def create_sku(
    data: SKUCreate,
    user: User = Depends(require_role(RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.PURCHASER)),
    db: AsyncSession = Depends(get_db),
):
    return await sku_svc.create_sku(db, data, user=user)


@router.patch("/{sku_id}", response_model=SKUDetail)
async def update_sku(
    sku_id: int,
    data: SKUUpdate,
    user: User = Depends(require_role(RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.PURCHASER)),
    db: AsyncSession = Depends(get_db),
):
    return await sku_svc.update_sku(db, sku_id, data, user=user)


@router.delete("/{sku_id}", status_code=204)
async def delete_sku(
    sku_id: int,
    user: User = Depends(require_role(RoleCode.ADMIN, RoleCode.MANAGER)),
    db: AsyncSession = Depends(get_db),
):
    await sku_svc.delete_sku(db, sku_id, user=user)
