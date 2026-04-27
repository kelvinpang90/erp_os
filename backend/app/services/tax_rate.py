from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.master import TaxRate
from app.models.organization import User
from app.repositories.tax_rate import TaxRateRepository
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.tax_rate import TaxRateCreate, TaxRateResponse, TaxRateUpdate


async def list_tax_rates(
    session: AsyncSession,
    pagination: PaginationParams,
    *,
    user: User,
    is_active: bool | None = None,
) -> PaginatedResponse[TaxRateResponse]:
    repo = TaxRateRepository(session)
    filters = [TaxRate.organization_id == user.organization_id]
    if is_active is not None:
        filters.append(TaxRate.is_active == is_active)

    items, total = await repo.list_all(
        filters=filters,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return PaginatedResponse.build(
        items=[TaxRateResponse.model_validate(t) for t in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


async def get_tax_rate(
    session: AsyncSession,
    tax_rate_id: int,
    *,
    user: User,
) -> TaxRateResponse:
    repo = TaxRateRepository(session)
    tax_rate = await repo.get_by_id(tax_rate_id)
    if not tax_rate or tax_rate.organization_id != user.organization_id:
        raise NotFoundError(message=f"TaxRate {tax_rate_id} not found.")
    return TaxRateResponse.model_validate(tax_rate)


async def create_tax_rate(
    session: AsyncSession,
    data: TaxRateCreate,
    *,
    user: User,
) -> TaxRateResponse:
    repo = TaxRateRepository(session)
    existing = await repo.get_by_code(user.organization_id, data.code)
    if existing:
        raise ConflictError(message=f"TaxRate with code '{data.code}' already exists.")

    if data.is_default:
        await repo.clear_default(user.organization_id)

    tax_rate = await repo.create(
        organization_id=user.organization_id,
        code=data.code,
        name=data.name,
        rate=data.rate,
        tax_type=data.tax_type,
        is_default=data.is_default,
    )
    return TaxRateResponse.model_validate(tax_rate)


async def update_tax_rate(
    session: AsyncSession,
    tax_rate_id: int,
    data: TaxRateUpdate,
    *,
    user: User,
) -> TaxRateResponse:
    repo = TaxRateRepository(session)
    tax_rate = await repo.get_by_id(tax_rate_id)
    if not tax_rate or tax_rate.organization_id != user.organization_id:
        raise NotFoundError(message=f"TaxRate {tax_rate_id} not found.")

    if data.code is not None and data.code != tax_rate.code:
        existing = await repo.get_by_code(user.organization_id, data.code)
        if existing:
            raise ConflictError(message=f"TaxRate with code '{data.code}' already exists.")

    if data.is_default:
        await repo.clear_default(user.organization_id)

    updates = data.model_dump(exclude_unset=True)
    tax_rate = await repo.update(tax_rate, **updates)
    return TaxRateResponse.model_validate(tax_rate)


async def delete_tax_rate(
    session: AsyncSession,
    tax_rate_id: int,
    *,
    user: User,
) -> None:
    repo = TaxRateRepository(session)
    tax_rate = await repo.get_by_id(tax_rate_id)
    if not tax_rate or tax_rate.organization_id != user.organization_id:
        raise NotFoundError(message=f"TaxRate {tax_rate_id} not found.")
    await repo.update(tax_rate, is_active=False)
