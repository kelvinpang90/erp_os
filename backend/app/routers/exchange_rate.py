from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_role
from app.enums import RoleCode
from app.models.organization import User
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.exchange_rate import ExchangeRateCreate, ExchangeRateResponse, ExchangeRateUpdate
from app.services import exchange_rate as exchange_rate_svc

router = APIRouter()


@router.get("", response_model=PaginatedResponse[ExchangeRateResponse])
async def list_exchange_rates(
    pagination: PaginationParams = Depends(),
    from_currency: Optional[str] = Query(default=None),
    to_currency: Optional[str] = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await exchange_rate_svc.list_exchange_rates(
        db, pagination, user=user, from_currency=from_currency, to_currency=to_currency
    )


@router.get("/{rate_id}", response_model=ExchangeRateResponse)
async def get_exchange_rate(
    rate_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await exchange_rate_svc.get_exchange_rate(db, rate_id, user=user)


@router.post("", response_model=ExchangeRateResponse, status_code=201)
async def create_exchange_rate(
    data: ExchangeRateCreate,
    user: User = Depends(require_role(RoleCode.ADMIN, RoleCode.MANAGER)),
    db: AsyncSession = Depends(get_db),
):
    return await exchange_rate_svc.create_exchange_rate(db, data, user=user)


@router.patch("/{rate_id}", response_model=ExchangeRateResponse)
async def update_exchange_rate(
    rate_id: int,
    data: ExchangeRateUpdate,
    user: User = Depends(require_role(RoleCode.ADMIN, RoleCode.MANAGER)),
    db: AsyncSession = Depends(get_db),
):
    return await exchange_rate_svc.update_exchange_rate(db, rate_id, data, user=user)
