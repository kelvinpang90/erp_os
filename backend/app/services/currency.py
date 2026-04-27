from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.organization import User
from app.repositories.currency import CurrencyRepository
from app.schemas.currency import CurrencyCreate, CurrencyResponse, CurrencyUpdate


async def list_currencies(
    session: AsyncSession,
    *,
    is_active: bool | None = None,
) -> list[CurrencyResponse]:
    repo = CurrencyRepository(session)
    if is_active is False:
        from app.models.master import Currency
        from sqlalchemy import select
        stmt = select(Currency)
        result = await session.execute(stmt)
        items = list(result.scalars().all())
    else:
        items = await repo.list_active()
    return [CurrencyResponse.model_validate(c) for c in items]


async def get_currency(
    session: AsyncSession,
    code: str,
) -> CurrencyResponse:
    repo = CurrencyRepository(session)
    currency = await repo.get_by_code(code)
    if not currency:
        raise NotFoundError(message=f"Currency '{code}' not found.")
    return CurrencyResponse.model_validate(currency)


async def create_currency(
    session: AsyncSession,
    data: CurrencyCreate,
    *,
    user: User,  # noqa: ARG001 — kept for audit trail consistency
) -> CurrencyResponse:
    repo = CurrencyRepository(session)
    existing = await repo.get_by_code(data.code)
    if existing:
        raise ConflictError(message=f"Currency '{data.code}' already exists.")

    from app.models.master import Currency
    currency = Currency(
        code=data.code,
        name=data.name,
        symbol=data.symbol,
        decimal_places=data.decimal_places,
        is_active=data.is_active,
    )
    session.add(currency)
    await session.flush()
    await session.refresh(currency)
    return CurrencyResponse.model_validate(currency)


async def update_currency(
    session: AsyncSession,
    code: str,
    data: CurrencyUpdate,
    *,
    user: User,  # noqa: ARG001
) -> CurrencyResponse:
    repo = CurrencyRepository(session)
    currency = await repo.get_by_code(code)
    if not currency:
        raise NotFoundError(message=f"Currency '{code}' not found.")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(currency, key, value)
    session.add(currency)
    await session.flush()
    await session.refresh(currency)
    return CurrencyResponse.model_validate(currency)
