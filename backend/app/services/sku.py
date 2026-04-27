from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.redis import redis_default
from app.models.organization import User
from app.repositories.sku import SKURepository
from app.repositories.tax_rate import TaxRateRepository
from app.repositories.uom import UOMRepository
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.sku import SKUCreate, SKUDetail, SKUResponse, SKUUpdate


async def list_skus(
    session: AsyncSession,
    pagination: PaginationParams,
    *,
    user: User,
    brand_id: int | None = None,
    category_id: int | None = None,
    is_active: bool | None = None,
    search: str | None = None,
) -> PaginatedResponse[SKUResponse]:
    repo = SKURepository(session)
    items, total = await repo.list_with_filters(
        user.organization_id,
        brand_id=brand_id,
        category_id=category_id,
        is_active=is_active,
        search=search,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return PaginatedResponse.build(
        items=[SKUResponse.model_validate(s) for s in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


async def get_sku(
    session: AsyncSession,
    sku_id: int,
    *,
    user: User,
) -> SKUDetail:
    repo = SKURepository(session)
    sku = await repo.get_detail(sku_id)
    if not sku or sku.organization_id != user.organization_id:
        raise NotFoundError(message=f"SKU {sku_id} not found.")
    return SKUDetail.model_validate(sku)


async def create_sku(
    session: AsyncSession,
    data: SKUCreate,
    *,
    user: User,
) -> SKUDetail:
    repo = SKURepository(session)

    if not data.code:
        seq = await redis_default.incr(f"seq:{user.organization_id}:sku")
        data.code = f"SKU-{seq:05d}"

    existing = await repo.get_by_code(user.organization_id, data.code)
    if existing:
        raise ConflictError(message=f"SKU with code '{data.code}' already exists.")

    uom_repo = UOMRepository(session)
    uom = await uom_repo.get_by_id(data.base_uom_id)
    if not uom or uom.organization_id != user.organization_id:
        raise NotFoundError(message=f"UOM {data.base_uom_id} not found.")

    tax_repo = TaxRateRepository(session)
    tax = await tax_repo.get_by_id(data.tax_rate_id)
    if not tax or tax.organization_id != user.organization_id:
        raise NotFoundError(message=f"TaxRate {data.tax_rate_id} not found.")

    sku = await repo.create(
        organization_id=user.organization_id,
        created_by=user.id,
        updated_by=user.id,
        **data.model_dump(),
    )
    sku = await repo.get_detail(sku.id)
    return SKUDetail.model_validate(sku)


async def update_sku(
    session: AsyncSession,
    sku_id: int,
    data: SKUUpdate,
    *,
    user: User,
) -> SKUDetail:
    repo = SKURepository(session)
    sku = await repo.get_by_id(sku_id)
    if not sku or sku.organization_id != user.organization_id or sku.deleted_at is not None:
        raise NotFoundError(message=f"SKU {sku_id} not found.")

    if data.base_uom_id is not None:
        uom_repo = UOMRepository(session)
        uom = await uom_repo.get_by_id(data.base_uom_id)
        if not uom or uom.organization_id != user.organization_id:
            raise NotFoundError(message=f"UOM {data.base_uom_id} not found.")

    if data.tax_rate_id is not None:
        tax_repo = TaxRateRepository(session)
        tax = await tax_repo.get_by_id(data.tax_rate_id)
        if not tax or tax.organization_id != user.organization_id:
            raise NotFoundError(message=f"TaxRate {data.tax_rate_id} not found.")

    updates = data.model_dump(exclude_unset=True)
    updates["updated_by"] = user.id
    await repo.update(sku, **updates)

    sku = await repo.get_detail(sku_id)
    return SKUDetail.model_validate(sku)


async def delete_sku(
    session: AsyncSession,
    sku_id: int,
    *,
    user: User,
) -> None:
    repo = SKURepository(session)
    sku = await repo.get_by_id(sku_id)
    if not sku or sku.organization_id != user.organization_id or sku.deleted_at is not None:
        raise NotFoundError(message=f"SKU {sku_id} not found.")
    await repo.soft_delete(sku)
