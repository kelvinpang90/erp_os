from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.master import Brand
from app.models.organization import User
from app.repositories.brand import BrandRepository
from app.schemas.brand import BrandCreate, BrandResponse, BrandUpdate
from app.schemas.common import PaginatedResponse, PaginationParams


async def list_brands(
    session: AsyncSession,
    pagination: PaginationParams,
    *,
    user: User,
    is_active: bool | None = None,
) -> PaginatedResponse[BrandResponse]:
    repo = BrandRepository(session)
    filters = [Brand.organization_id == user.organization_id]
    if is_active is not None:
        filters.append(Brand.is_active == is_active)

    items, total = await repo.list_all(
        filters=filters,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return PaginatedResponse.build(
        items=[BrandResponse.model_validate(b) for b in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


async def get_brand(
    session: AsyncSession,
    brand_id: int,
    *,
    user: User,
) -> BrandResponse:
    repo = BrandRepository(session)
    brand = await repo.get_by_id(brand_id)
    if not brand or brand.organization_id != user.organization_id or brand.deleted_at is not None:
        raise NotFoundError(message=f"Brand {brand_id} not found.")
    return BrandResponse.model_validate(brand)


async def create_brand(
    session: AsyncSession,
    data: BrandCreate,
    *,
    user: User,
) -> BrandResponse:
    repo = BrandRepository(session)
    existing = await repo.get_by_code(user.organization_id, data.code)
    if existing:
        raise ConflictError(message=f"Brand with code '{data.code}' already exists.")

    brand = await repo.create(
        organization_id=user.organization_id,
        code=data.code,
        name=data.name,
        logo_url=data.logo_url,
    )
    return BrandResponse.model_validate(brand)


async def update_brand(
    session: AsyncSession,
    brand_id: int,
    data: BrandUpdate,
    *,
    user: User,
) -> BrandResponse:
    repo = BrandRepository(session)
    brand = await repo.get_by_id(brand_id)
    if not brand or brand.organization_id != user.organization_id or brand.deleted_at is not None:
        raise NotFoundError(message=f"Brand {brand_id} not found.")

    if data.code is not None and data.code != brand.code:
        existing = await repo.get_by_code(user.organization_id, data.code)
        if existing:
            raise ConflictError(message=f"Brand with code '{data.code}' already exists.")

    updates = data.model_dump(exclude_unset=True)
    brand = await repo.update(brand, **updates)
    return BrandResponse.model_validate(brand)


async def delete_brand(
    session: AsyncSession,
    brand_id: int,
    *,
    user: User,
) -> None:
    repo = BrandRepository(session)
    brand = await repo.get_by_id(brand_id)
    if not brand or brand.organization_id != user.organization_id or brand.deleted_at is not None:
        raise NotFoundError(message=f"Brand {brand_id} not found.")
    await repo.soft_delete(brand)
