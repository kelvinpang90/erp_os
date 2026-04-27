from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.master import UOM
from app.models.organization import User
from app.repositories.uom import UOMRepository
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.uom import UOMCreate, UOMResponse, UOMUpdate


async def list_uoms(
    session: AsyncSession,
    pagination: PaginationParams,
    *,
    user: User,
    is_active: bool | None = None,
) -> PaginatedResponse[UOMResponse]:
    repo = UOMRepository(session)
    filters = [UOM.organization_id == user.organization_id]
    if is_active is not None:
        filters.append(UOM.is_active == is_active)

    items, total = await repo.list_all(
        filters=filters,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return PaginatedResponse.build(
        items=[UOMResponse.model_validate(u) for u in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


async def get_uom(
    session: AsyncSession,
    uom_id: int,
    *,
    user: User,
) -> UOMResponse:
    repo = UOMRepository(session)
    uom = await repo.get_by_id(uom_id)
    if not uom or uom.organization_id != user.organization_id:
        raise NotFoundError(message=f"UOM {uom_id} not found.")
    return UOMResponse.model_validate(uom)


async def create_uom(
    session: AsyncSession,
    data: UOMCreate,
    *,
    user: User,
) -> UOMResponse:
    repo = UOMRepository(session)
    existing = await repo.get_by_code(user.organization_id, data.code)
    if existing:
        raise ConflictError(message=f"UOM with code '{data.code}' already exists.")

    uom = await repo.create(
        organization_id=user.organization_id,
        code=data.code,
        name=data.name,
        name_zh=data.name_zh,
    )
    return UOMResponse.model_validate(uom)


async def update_uom(
    session: AsyncSession,
    uom_id: int,
    data: UOMUpdate,
    *,
    user: User,
) -> UOMResponse:
    repo = UOMRepository(session)
    uom = await repo.get_by_id(uom_id)
    if not uom or uom.organization_id != user.organization_id:
        raise NotFoundError(message=f"UOM {uom_id} not found.")

    if data.code is not None and data.code != uom.code:
        existing = await repo.get_by_code(user.organization_id, data.code)
        if existing:
            raise ConflictError(message=f"UOM with code '{data.code}' already exists.")

    updates = data.model_dump(exclude_unset=True)
    uom = await repo.update(uom, **updates)
    return UOMResponse.model_validate(uom)


async def delete_uom(
    session: AsyncSession,
    uom_id: int,
    *,
    user: User,
) -> None:
    repo = UOMRepository(session)
    uom = await repo.get_by_id(uom_id)
    if not uom or uom.organization_id != user.organization_id:
        raise NotFoundError(message=f"UOM {uom_id} not found.")
    # UOM has no soft-delete mixin; mark inactive instead
    await repo.update(uom, is_active=False)
