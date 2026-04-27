from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.enums import CustomerType
from app.models.organization import User
from app.repositories.customer import CustomerRepository
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.customer import (
    CustomerCreate,
    CustomerDetail,
    CustomerResponse,
    CustomerUpdate,
)


async def list_customers(
    session: AsyncSession,
    pagination: PaginationParams,
    *,
    org_id: int,
    search: str | None = None,
    customer_type: CustomerType | None = None,
    is_active: bool | None = None,
) -> PaginatedResponse[CustomerResponse]:
    repo = CustomerRepository(session)
    items, total = await repo.list_with_filters(
        org_id,
        customer_type=customer_type,
        search=search,
        is_active=is_active,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return PaginatedResponse[CustomerResponse].build(
        items=[CustomerResponse.model_validate(c) for c in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


async def get_customer(
    session: AsyncSession,
    customer_id: int,
    *,
    org_id: int,
) -> CustomerDetail:
    repo = CustomerRepository(session)
    customer = await repo.get_detail(org_id, customer_id)
    if customer is None:
        raise NotFoundError(f"Customer {customer_id} not found.")
    return CustomerDetail.model_validate(customer)


async def create_customer(
    session: AsyncSession,
    data: CustomerCreate,
    *,
    org_id: int,
    user: User,
) -> CustomerDetail:
    repo = CustomerRepository(session)
    existing = await repo.get_by_code(org_id, data.code)
    if existing is not None:
        raise ConflictError(f"Customer code '{data.code}' already exists.")

    customer = await repo.create(
        organization_id=org_id,
        created_by=user.id,
        updated_by=user.id,
        **data.model_dump(),
    )
    return await get_customer(session, customer.id, org_id=org_id)


async def update_customer(
    session: AsyncSession,
    customer_id: int,
    data: CustomerUpdate,
    *,
    org_id: int,
    user: User,
) -> CustomerDetail:
    repo = CustomerRepository(session)
    customer = await repo.get_detail(org_id, customer_id)
    if customer is None:
        raise NotFoundError(f"Customer {customer_id} not found.")

    updates = data.model_dump(exclude_unset=True)
    updates["updated_by"] = user.id
    await repo.update(customer, **updates)
    return await get_customer(session, customer_id, org_id=org_id)


async def delete_customer(
    session: AsyncSession,
    customer_id: int,
    *,
    org_id: int,
    user: User,
) -> None:
    repo = CustomerRepository(session)
    customer = await repo.get_detail(org_id, customer_id)
    if customer is None:
        raise NotFoundError(f"Customer {customer_id} not found.")
    await repo.soft_delete(customer)
