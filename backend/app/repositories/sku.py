from __future__ import annotations

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.master import Brand, Category, TaxRate, UOM
from app.models.sku import SKU
from app.repositories.base import BaseRepository


class SKURepository(BaseRepository[SKU]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(SKU, session)

    async def get_by_code(self, org_id: int, code: str) -> SKU | None:
        stmt = select(SKU).where(
            and_(
                SKU.organization_id == org_id,
                SKU.code == code,
                SKU.deleted_at.is_(None),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_detail(self, sku_id: int) -> SKU | None:
        stmt = (
            select(SKU)
            .where(and_(SKU.id == sku_id, SKU.deleted_at.is_(None)))
            .options(
                selectinload(SKU.brand),
                selectinload(SKU.category),
                selectinload(SKU.base_uom),
                selectinload(SKU.tax_rate),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_with_filters(
        self,
        org_id: int,
        *,
        brand_id: int | None = None,
        category_id: int | None = None,
        is_active: bool | None = None,
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[SKU], int]:
        from sqlalchemy import func, or_

        filters = [
            SKU.organization_id == org_id,
            SKU.deleted_at.is_(None),
        ]
        if brand_id is not None:
            filters.append(SKU.brand_id == brand_id)
        if category_id is not None:
            filters.append(SKU.category_id == category_id)
        if is_active is not None:
            filters.append(SKU.is_active == is_active)
        if search:
            like = f"%{search}%"
            filters.append(
                or_(
                    SKU.code.ilike(like),
                    SKU.name.ilike(like),
                    SKU.barcode.ilike(like),
                )
            )

        stmt = (
            select(SKU)
            .where(and_(*filters))
            .options(
                selectinload(SKU.brand),
                selectinload(SKU.category),
                selectinload(SKU.base_uom),
                selectinload(SKU.tax_rate),
            )
            .order_by(SKU.code)
            .limit(limit)
            .offset(offset)
        )
        count_stmt = (
            select(func.count())
            .select_from(SKU)
            .where(and_(*filters))
        )

        total_result = await self.session.execute(count_stmt)
        total: int = total_result.scalar_one()

        result = await self.session.execute(stmt)
        items = list(result.scalars().all())

        return items, total
