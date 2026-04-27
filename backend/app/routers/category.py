from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_role
from app.enums import RoleCode
from app.models.organization import User
from app.schemas.category import CategoryCreate, CategoryResponse, CategoryUpdate
from app.schemas.common import PaginatedResponse, PaginationParams
from app.services import category as category_svc

router = APIRouter()


@router.get("", response_model=PaginatedResponse[CategoryResponse])
async def list_categories(
    pagination: PaginationParams = Depends(),
    parent_id: Optional[int] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await category_svc.list_categories(
        db, pagination, user=user, parent_id=parent_id, is_active=is_active
    )


@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category(
    category_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await category_svc.get_category(db, category_id, user=user)


@router.post("", response_model=CategoryResponse, status_code=201)
async def create_category(
    data: CategoryCreate,
    user: User = Depends(require_role(RoleCode.ADMIN, RoleCode.MANAGER)),
    db: AsyncSession = Depends(get_db),
):
    return await category_svc.create_category(db, data, user=user)


@router.patch("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: int,
    data: CategoryUpdate,
    user: User = Depends(require_role(RoleCode.ADMIN, RoleCode.MANAGER)),
    db: AsyncSession = Depends(get_db),
):
    return await category_svc.update_category(db, category_id, data, user=user)


@router.delete("/{category_id}", status_code=204)
async def delete_category(
    category_id: int,
    user: User = Depends(require_role(RoleCode.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    await category_svc.delete_category(db, category_id, user=user)
