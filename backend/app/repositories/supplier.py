from __future__ import annotations

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.partner import Supplier
from app.repositories.base import BaseRepository


class SupplierRepository(BaseRepository[Supplier]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Supplier, session)

    async def get_by_code(self, org_id: int, code: str) -> Supplier | None:
        """Check code uniqueness including soft-deleted records to prevent reuse."""
        stmt = select(Supplier).where(
            and_(
                Supplier.organization_id == org_id,
                Supplier.code == code,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_detail(self, org_id: int, supplier_id: int) -> Supplier | None:
        stmt = select(Supplier).where(
            and_(
                Supplier.id == supplier_id,
                Supplier.organization_id == org_id,
                Supplier.deleted_at.is_(None),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_with_filters(
        self,
        org_id: int,
        *,
        is_active: bool | None = None,
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Supplier], int]:
        filters = [
            Supplier.organization_id == org_id,
            Supplier.deleted_at.is_(None),
        ]
        if is_active is not None:
            filters.append(Supplier.is_active == is_active)
        if search:
            like = f"%{search}%"
            filters.append(
                or_(
                    Supplier.code.ilike(like),
                    Supplier.name.ilike(like),
                    Supplier.contact_person.ilike(like),
                    Supplier.email.ilike(like),
                )
            )

        count_stmt = select(func.count()).select_from(Supplier).where(and_(*filters))
        stmt = (
            select(Supplier)
            .where(and_(*filters))
            .order_by(Supplier.code)
            .limit(limit)
            .offset(offset)
        )

        total_result = await self.session.execute(count_stmt)
        total: int = total_result.scalar_one()

        result = await self.session.execute(stmt)
        items = list(result.scalars().all())

        return items, total
