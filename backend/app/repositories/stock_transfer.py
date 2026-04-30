"""Stock Transfer repository — query helpers for service layer."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.enums import StockTransferStatus
from app.models.stock import StockTransfer, StockTransferLine
from app.repositories.base import BaseRepository


class StockTransferRepository(BaseRepository[StockTransfer]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(StockTransfer, session)

    async def get_detail(
        self, org_id: int, transfer_id: int
    ) -> Optional[StockTransfer]:
        stmt = (
            select(StockTransfer)
            .where(
                StockTransfer.id == transfer_id,
                StockTransfer.organization_id == org_id,
                StockTransfer.deleted_at.is_(None),
            )
            .options(
                selectinload(StockTransfer.lines).selectinload(StockTransferLine.sku),
                selectinload(StockTransfer.from_warehouse),
                selectinload(StockTransfer.to_warehouse),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_with_filters(
        self,
        org_id: int,
        *,
        status: Optional[StockTransferStatus] = None,
        from_warehouse_id: Optional[int] = None,
        to_warehouse_id: Optional[int] = None,
        search: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[StockTransfer], int]:
        filters = [
            StockTransfer.organization_id == org_id,
            StockTransfer.deleted_at.is_(None),
        ]
        if status is not None:
            filters.append(StockTransfer.status == status)
        if from_warehouse_id is not None:
            filters.append(StockTransfer.from_warehouse_id == from_warehouse_id)
        if to_warehouse_id is not None:
            filters.append(StockTransfer.to_warehouse_id == to_warehouse_id)
        if search:
            like = f"%{search}%"
            filters.append(
                or_(
                    StockTransfer.document_no.ilike(like),
                    StockTransfer.remarks.ilike(like),
                )
            )

        where_clause = and_(*filters)
        count_stmt = select(func.count()).select_from(StockTransfer).where(where_clause)
        stmt = (
            select(StockTransfer)
            .where(where_clause)
            .order_by(
                StockTransfer.business_date.desc(),
                StockTransfer.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )

        total = (await self.session.execute(count_stmt)).scalar_one()
        items = list((await self.session.execute(stmt)).scalars().all())
        return items, total
