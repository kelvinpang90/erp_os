"""Stock Adjustment repository."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.enums import StockAdjustmentStatus
from app.models.stock import StockAdjustment, StockAdjustmentLine
from app.repositories.base import BaseRepository


class StockAdjustmentRepository(BaseRepository[StockAdjustment]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(StockAdjustment, session)

    async def get_detail(
        self, org_id: int, adj_id: int
    ) -> Optional[StockAdjustment]:
        stmt = (
            select(StockAdjustment)
            .where(
                StockAdjustment.id == adj_id,
                StockAdjustment.organization_id == org_id,
                StockAdjustment.deleted_at.is_(None),
            )
            .options(
                selectinload(StockAdjustment.lines).selectinload(
                    StockAdjustmentLine.sku
                ),
                selectinload(StockAdjustment.warehouse),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_with_filters(
        self,
        org_id: int,
        *,
        status: Optional[StockAdjustmentStatus] = None,
        warehouse_id: Optional[int] = None,
        search: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[StockAdjustment], int]:
        filters = [
            StockAdjustment.organization_id == org_id,
            StockAdjustment.deleted_at.is_(None),
        ]
        if status is not None:
            filters.append(StockAdjustment.status == status)
        if warehouse_id is not None:
            filters.append(StockAdjustment.warehouse_id == warehouse_id)
        if search:
            like = f"%{search}%"
            filters.append(
                or_(
                    StockAdjustment.document_no.ilike(like),
                    StockAdjustment.remarks.ilike(like),
                )
            )

        where_clause = and_(*filters)
        count_stmt = (
            select(func.count()).select_from(StockAdjustment).where(where_clause)
        )
        stmt = (
            select(StockAdjustment)
            .where(where_clause)
            .order_by(
                StockAdjustment.business_date.desc(),
                StockAdjustment.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )

        total = (await self.session.execute(count_stmt)).scalar_one()
        items = list((await self.session.execute(stmt)).scalars().all())
        return items, total
