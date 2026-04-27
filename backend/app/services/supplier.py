from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.organization import User
from app.repositories.supplier import SupplierRepository
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.supplier import (
    SupplierCreate,
    SupplierDetail,
    SupplierPOStats,
    SupplierResponse,
    SupplierUpdate,
)


async def list_suppliers(
    session: AsyncSession,
    pagination: PaginationParams,
    *,
    org_id: int,
    search: str | None = None,
    is_active: bool | None = None,
) -> PaginatedResponse[SupplierResponse]:
    repo = SupplierRepository(session)
    items, total = await repo.list_with_filters(
        org_id,
        search=search,
        is_active=is_active,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return PaginatedResponse[SupplierResponse].build(
        items=[SupplierResponse.model_validate(s) for s in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


async def get_supplier(
    session: AsyncSession,
    supplier_id: int,
    *,
    org_id: int,
) -> SupplierDetail:
    repo = SupplierRepository(session)
    supplier = await repo.get_detail(org_id, supplier_id)
    if supplier is None:
        raise NotFoundError(f"Supplier {supplier_id} not found.")
    detail = SupplierDetail.model_validate(supplier)
    detail.po_stats = SupplierPOStats()
    return detail


async def create_supplier(
    session: AsyncSession,
    data: SupplierCreate,
    *,
    org_id: int,
    user: User,
) -> SupplierDetail:
    repo = SupplierRepository(session)
    existing = await repo.get_by_code(org_id, data.code)
    if existing is not None:
        raise ConflictError(f"Supplier code '{data.code}' already exists.")

    supplier = await repo.create(
        organization_id=org_id,
        created_by=user.id,
        updated_by=user.id,
        **data.model_dump(),
    )
    return await get_supplier(session, supplier.id, org_id=org_id)


async def update_supplier(
    session: AsyncSession,
    supplier_id: int,
    data: SupplierUpdate,
    *,
    org_id: int,
    user: User,
) -> SupplierDetail:
    repo = SupplierRepository(session)
    supplier = await repo.get_detail(org_id, supplier_id)
    if supplier is None:
        raise NotFoundError(f"Supplier {supplier_id} not found.")

    updates = data.model_dump(exclude_unset=True)
    updates["updated_by"] = user.id
    await repo.update(supplier, **updates)
    return await get_supplier(session, supplier_id, org_id=org_id)


async def delete_supplier(
    session: AsyncSession,
    supplier_id: int,
    *,
    org_id: int,
    user: User,
) -> None:
    repo = SupplierRepository(session)
    supplier = await repo.get_detail(org_id, supplier_id)
    if supplier is None:
        raise NotFoundError(f"Supplier {supplier_id} not found.")
    await repo.soft_delete(supplier)
