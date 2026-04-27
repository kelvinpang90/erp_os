from __future__ import annotations

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import CustomerType
from app.models.partner import Customer
from app.repositories.base import BaseRepository


class CustomerRepository(BaseRepository[Customer]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Customer, session)

    async def get_by_code(self, org_id: int, code: str) -> Customer | None:
        """Check code uniqueness including soft-deleted records to prevent reuse."""
        stmt = select(Customer).where(
            and_(
                Customer.organization_id == org_id,
                Customer.code == code,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_detail(self, org_id: int, customer_id: int) -> Customer | None:
        stmt = select(Customer).where(
            and_(
                Customer.id == customer_id,
                Customer.organization_id == org_id,
                Customer.deleted_at.is_(None),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_with_filters(
        self,
        org_id: int,
        *,
        customer_type: CustomerType | None = None,
        is_active: bool | None = None,
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Customer], int]:
        filters = [
            Customer.organization_id == org_id,
            Customer.deleted_at.is_(None),
        ]
        if customer_type is not None:
            filters.append(Customer.customer_type == customer_type)
        if is_active is not None:
            filters.append(Customer.is_active == is_active)
        if search:
            like = f"%{search}%"
            filters.append(
                or_(
                    Customer.code.ilike(like),
                    Customer.name.ilike(like),
                    Customer.contact_person.ilike(like),
                    Customer.email.ilike(like),
                )
            )

        count_stmt = select(func.count()).select_from(Customer).where(and_(*filters))
        stmt = (
            select(Customer)
            .where(and_(*filters))
            .order_by(Customer.code)
            .limit(limit)
            .offset(offset)
        )

        total_result = await self.session.execute(count_stmt)
        total: int = total_result.scalar_one()

        result = await self.session.execute(stmt)
        items = list(result.scalars().all())

        return items, total
