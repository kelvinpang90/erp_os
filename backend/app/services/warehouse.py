from __future__ import annotations

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.enums import WarehouseType
from app.models.organization import User, Warehouse
from app.repositories.warehouse import WarehouseRepository
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.warehouse import (
    WarehouseCreate,
    WarehouseDetail,
    WarehouseResponse,
    WarehouseUpdate,
)


def _to_response(wh: Warehouse) -> WarehouseResponse:
    data = WarehouseResponse.model_validate(wh)
    if wh.manager is not None:
        data.manager_name = wh.manager.full_name
    return data


def _to_detail(wh: Warehouse) -> WarehouseDetail:
    data = WarehouseDetail.model_validate(wh)
    if wh.manager is not None:
        data.manager_name = wh.manager.full_name
    return data


async def list_warehouses(
    session: AsyncSession,
    pagination: PaginationParams,
    *,
    org_id: int,
    include_inactive: bool = False,
) -> PaginatedResponse[WarehouseResponse]:
    repo = WarehouseRepository(session)
    items, total = await repo.list_with_filters(
        org_id,
        include_inactive=include_inactive,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return PaginatedResponse[WarehouseResponse].build(
        items=[_to_response(wh) for wh in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


async def get_all_active(
    session: AsyncSession,
    *,
    org_id: int,
) -> list[WarehouseResponse]:
    repo = WarehouseRepository(session)
    items = await repo.get_all_active(org_id)
    return [_to_response(wh) for wh in items]


async def get_warehouse(
    session: AsyncSession,
    warehouse_id: int,
    *,
    org_id: int,
) -> WarehouseDetail:
    repo = WarehouseRepository(session)
    wh = await repo.get_detail(org_id, warehouse_id)
    if wh is None:
        raise NotFoundError(f"Warehouse {warehouse_id} not found.")
    return _to_detail(wh)


async def _validate_manager(
    session: AsyncSession,
    manager_user_id: int,
    org_id: int,
) -> None:
    stmt = select(User).where(
        and_(User.id == manager_user_id, User.organization_id == org_id)
    )
    result = await session.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise NotFoundError(
            f"User {manager_user_id} not found in this organization.",
            error_code="MANAGER_NOT_IN_ORG",
        )


async def create_warehouse(
    session: AsyncSession,
    data: WarehouseCreate,
    *,
    org_id: int,
    user: User,
) -> WarehouseDetail:
    repo = WarehouseRepository(session)
    existing = await repo.get_by_code(org_id, data.code)
    if existing is not None:
        raise ConflictError(f"Warehouse code '{data.code}' already exists.")

    if data.manager_user_id is not None:
        await _validate_manager(session, data.manager_user_id, org_id)

    wh = await repo.create(
        organization_id=org_id,
        **data.model_dump(),
    )
    return await get_warehouse(session, wh.id, org_id=org_id)


async def update_warehouse(
    session: AsyncSession,
    warehouse_id: int,
    data: WarehouseUpdate,
    *,
    org_id: int,
    user: User,
) -> WarehouseDetail:
    repo = WarehouseRepository(session)
    wh = await repo.get_detail(org_id, warehouse_id)
    if wh is None:
        raise NotFoundError(f"Warehouse {warehouse_id} not found.")

    updates = data.model_dump(exclude_unset=True)
    if "manager_user_id" in updates and updates["manager_user_id"] is not None:
        await _validate_manager(session, updates["manager_user_id"], org_id)

    await repo.update(wh, **updates)
    return await get_warehouse(session, warehouse_id, org_id=org_id)


async def delete_warehouse(
    session: AsyncSession,
    warehouse_id: int,
    *,
    org_id: int,
    user: User,
) -> None:
    repo = WarehouseRepository(session)
    wh = await repo.get_detail(org_id, warehouse_id)
    if wh is None:
        raise NotFoundError(f"Warehouse {warehouse_id} not found.")

    if wh.type == WarehouseType.MAIN:
        raise BusinessRuleError(
            "Main warehouse cannot be deleted.",
            error_code="WAREHOUSE_MAIN_DELETE_FORBIDDEN",
        )

    await repo.soft_delete(wh)
