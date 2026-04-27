from __future__ import annotations

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.organization import Warehouse
from app.repositories.base import BaseRepository


class WarehouseRepository(BaseRepository[Warehouse]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Warehouse, session)

    async def get_by_code(self, org_id: int, code: str) -> Warehouse | None:
        """Check code uniqueness including soft-deleted records to prevent reuse."""
        stmt = select(Warehouse).where(
            and_(
                Warehouse.organization_id == org_id,
                Warehouse.code == code,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_detail(self, org_id: int, warehouse_id: int) -> Warehouse | None:
        stmt = (
            select(Warehouse)
            .where(
                and_(
                    Warehouse.id == warehouse_id,
                    Warehouse.organization_id == org_id,
                    Warehouse.deleted_at.is_(None),
                )
            )
            .options(selectinload(Warehouse.manager))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_with_filters(
        self,
        org_id: int,
        *,
        include_inactive: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Warehouse], int]:
        filters = [
            Warehouse.organization_id == org_id,
            Warehouse.deleted_at.is_(None),
        ]
        if not include_inactive:
            filters.append(Warehouse.is_active.is_(True))

        count_stmt = select(func.count()).select_from(Warehouse).where(and_(*filters))
        stmt = (
            select(Warehouse)
            .where(and_(*filters))
            .options(selectinload(Warehouse.manager))
            .order_by(Warehouse.code)
            .limit(limit)
            .offset(offset)
        )

        total_result = await self.session.execute(count_stmt)
        total: int = total_result.scalar_one()

        result = await self.session.execute(stmt)
        items = list(result.scalars().all())

        return items, total

    async def get_all_active(self, org_id: int) -> list[Warehouse]:
        stmt = (
            select(Warehouse)
            .where(
                and_(
                    Warehouse.organization_id == org_id,
                    Warehouse.is_active.is_(True),
                    Warehouse.deleted_at.is_(None),
                )
            )
            .options(selectinload(Warehouse.manager))
            .order_by(Warehouse.code)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
