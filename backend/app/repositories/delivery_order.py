"""Repository for DeliveryOrder (Window 10)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.sales import DeliveryOrder, DeliveryOrderLine
from app.repositories.base import BaseRepository


class DeliveryOrderRepository(BaseRepository[DeliveryOrder]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(DeliveryOrder, session)

    async def get_detail(self, org_id: int, do_id: int) -> Optional[DeliveryOrder]:
        stmt = (
            select(DeliveryOrder)
            .where(
                DeliveryOrder.id == do_id,
                DeliveryOrder.organization_id == org_id,
                DeliveryOrder.deleted_at.is_(None),
            )
            .options(
                selectinload(DeliveryOrder.lines).selectinload(DeliveryOrderLine.sku),
                selectinload(DeliveryOrder.lines).selectinload(DeliveryOrderLine.sales_order_line),
                selectinload(DeliveryOrder.sales_order),
                selectinload(DeliveryOrder.warehouse),
                selectinload(DeliveryOrder.deliverer),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_document_no(self, org_id: int, document_no: str) -> Optional[DeliveryOrder]:
        stmt = select(DeliveryOrder).where(
            DeliveryOrder.organization_id == org_id,
            DeliveryOrder.document_no == document_no,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_with_filters(
        self,
        org_id: int,
        *,
        sales_order_id: Optional[int] = None,
        warehouse_id: Optional[int] = None,
        search: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[DeliveryOrder], int]:
        filters = [
            DeliveryOrder.organization_id == org_id,
            DeliveryOrder.deleted_at.is_(None),
        ]
        if sales_order_id is not None:
            filters.append(DeliveryOrder.sales_order_id == sales_order_id)
        if warehouse_id is not None:
            filters.append(DeliveryOrder.warehouse_id == warehouse_id)
        if search:
            like = f"%{search}%"
            filters.append(
                or_(
                    DeliveryOrder.document_no.ilike(like),
                    DeliveryOrder.tracking_no.ilike(like),
                    DeliveryOrder.remarks.ilike(like),
                )
            )

        where_clause = and_(*filters)
        count_stmt = select(func.count()).select_from(DeliveryOrder).where(where_clause)
        stmt = (
            select(DeliveryOrder)
            .where(where_clause)
            .options(selectinload(DeliveryOrder.sales_order))
            .order_by(DeliveryOrder.delivery_date.desc(), DeliveryOrder.id.desc())
            .limit(limit)
            .offset(offset)
        )

        total = (await self.session.execute(count_stmt)).scalar_one()
        items = list((await self.session.execute(stmt)).scalars().all())
        return items, total
