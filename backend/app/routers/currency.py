from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_role
from app.enums import RoleCode
from app.models.organization import User
from app.schemas.currency import CurrencyCreate, CurrencyResponse, CurrencyUpdate
from app.services import currency as currency_svc

router = APIRouter()


@router.get("", response_model=list[CurrencyResponse])
async def list_currencies(
    is_active: Optional[bool] = Query(default=True),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await currency_svc.list_currencies(db, is_active=is_active)


@router.get("/{code}", response_model=CurrencyResponse)
async def get_currency(
    code: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await currency_svc.get_currency(db, code.upper())


@router.post("", response_model=CurrencyResponse, status_code=201)
async def create_currency(
    data: CurrencyCreate,
    user: User = Depends(require_role(RoleCode.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    return await currency_svc.create_currency(db, data, user=user)


@router.patch("/{code}", response_model=CurrencyResponse)
async def update_currency(
    code: str,
    data: CurrencyUpdate,
    user: User = Depends(require_role(RoleCode.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    return await currency_svc.update_currency(db, code.upper(), data, user=user)
