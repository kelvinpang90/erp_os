from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_role
from app.enums import RoleCode
from app.models.organization import User
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.uom import UOMCreate, UOMResponse, UOMUpdate
from app.services import uom as uom_svc

router = APIRouter()


@router.get("", response_model=PaginatedResponse[UOMResponse])
async def list_uoms(
    pagination: PaginationParams = Depends(),
    is_active: Optional[bool] = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await uom_svc.list_uoms(db, pagination, user=user, is_active=is_active)


@router.get("/{uom_id}", response_model=UOMResponse)
async def get_uom(
    uom_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await uom_svc.get_uom(db, uom_id, user=user)


@router.post("", response_model=UOMResponse, status_code=201)
async def create_uom(
    data: UOMCreate,
    user: User = Depends(require_role(RoleCode.ADMIN, RoleCode.MANAGER)),
    db: AsyncSession = Depends(get_db),
):
    return await uom_svc.create_uom(db, data, user=user)


@router.patch("/{uom_id}", response_model=UOMResponse)
async def update_uom(
    uom_id: int,
    data: UOMUpdate,
    user: User = Depends(require_role(RoleCode.ADMIN, RoleCode.MANAGER)),
    db: AsyncSession = Depends(get_db),
):
    return await uom_svc.update_uom(db, uom_id, data, user=user)


@router.delete("/{uom_id}", status_code=204)
async def delete_uom(
    uom_id: int,
    user: User = Depends(require_role(RoleCode.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    await uom_svc.delete_uom(db, uom_id, user=user)
