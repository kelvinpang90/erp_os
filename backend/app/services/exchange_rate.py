from __future__ import annotations

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.master import Currency, ExchangeRate
from app.models.organization import User
from app.repositories.exchange_rate import ExchangeRateRepository
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.exchange_rate import ExchangeRateCreate, ExchangeRateResponse, ExchangeRateUpdate


async def list_exchange_rates(
    session: AsyncSession,
    pagination: PaginationParams,
    *,
    user: User,
    from_currency: str | None = None,
    to_currency: str | None = None,
) -> PaginatedResponse[ExchangeRateResponse]:
    repo = ExchangeRateRepository(session)
    filters = [ExchangeRate.organization_id == user.organization_id]
    if from_currency:
        filters.append(ExchangeRate.from_currency == from_currency)
    if to_currency:
        filters.append(ExchangeRate.to_currency == to_currency)

    items, total = await repo.list_all(
        filters=filters,
        order_by=[ExchangeRate.effective_from.desc()],
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return PaginatedResponse.build(
        items=[ExchangeRateResponse.model_validate(r) for r in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


async def get_exchange_rate(
    session: AsyncSession,
    rate_id: int,
    *,
    user: User,
) -> ExchangeRateResponse:
    repo = ExchangeRateRepository(session)
    rate = await repo.get_by_id(rate_id)
    if not rate or rate.organization_id != user.organization_id:
        raise NotFoundError(message=f"ExchangeRate {rate_id} not found.")
    return ExchangeRateResponse.model_validate(rate)


async def create_exchange_rate(
    session: AsyncSession,
    data: ExchangeRateCreate,
    *,
    user: User,
) -> ExchangeRateResponse:
    for code in (data.from_currency, data.to_currency):
        currency = await session.get(Currency, code)
        if not currency:
            raise NotFoundError(message=f"Currency '{code}' not found.")

    rate = ExchangeRate(
        organization_id=user.organization_id,
        from_currency=data.from_currency,
        to_currency=data.to_currency,
        rate=data.rate,
        effective_from=data.effective_from,
        effective_to=data.effective_to,
        created_by=user.id,
    )
    session.add(rate)
    await session.flush()
    await session.refresh(rate)
    return ExchangeRateResponse.model_validate(rate)


async def update_exchange_rate(
    session: AsyncSession,
    rate_id: int,
    data: ExchangeRateUpdate,
    *,
    user: User,
) -> ExchangeRateResponse:
    repo = ExchangeRateRepository(session)
    rate = await repo.get_by_id(rate_id)
    if not rate or rate.organization_id != user.organization_id:
        raise NotFoundError(message=f"ExchangeRate {rate_id} not found.")

    updates = data.model_dump(exclude_unset=True)
    rate = await repo.update(rate, **updates)
    return ExchangeRateResponse.model_validate(rate)
