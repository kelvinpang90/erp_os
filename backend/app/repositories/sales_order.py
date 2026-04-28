from __future__ import annotations

from typing import Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.enums import SOStatus
from app.models.sales import SalesOrder, SalesOrderLine
from app.repositories.base import BaseRepository


class SalesOrderRepository(BaseRepository[SalesOrder]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(SalesOrder, session)

    async def get_detail(self, org_id: int, so_id: int) -> Optional[SalesOrder]:
        stmt = (
            select(SalesOrder)
            .where(
                SalesOrder.id == so_id,
                SalesOrder.organization_id == org_id,
                SalesOrder.deleted_at.is_(None),
            )
            .options(
                selectinload(SalesOrder.lines).selectinload(SalesOrderLine.sku),
                selectinload(SalesOrder.customer),
                selectinload(SalesOrder.warehouse),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_document_no(self, org_id: int, document_no: str) -> Optional[SalesOrder]:
        stmt = select(SalesOrder).where(
            SalesOrder.organization_id == org_id,
            SalesOrder.document_no == document_no,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_with_filters(
        self,
        org_id: int,
        *,
        status: Optional[SOStatus] = None,
        customer_id: Optional[int] = None,
        warehouse_id: Optional[int] = None,
        search: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[SalesOrder], int]:
        filters = [
            SalesOrder.organization_id == org_id,
            SalesOrder.deleted_at.is_(None),
        ]
        if status is not None:
            filters.append(SalesOrder.status == status)
        if customer_id is not None:
            filters.append(SalesOrder.customer_id == customer_id)
        if warehouse_id is not None:
            filters.append(SalesOrder.warehouse_id == warehouse_id)
        if search:
            like = f"%{search}%"
            filters.append(
                or_(
                    SalesOrder.document_no.ilike(like),
                    SalesOrder.remarks.ilike(like),
                )
            )

        where_clause = and_(*filters)
        count_stmt = select(func.count()).select_from(SalesOrder).where(where_clause)
        stmt = (
            select(SalesOrder)
            .where(where_clause)
            .order_by(SalesOrder.business_date.desc(), SalesOrder.id.desc())
            .limit(limit)
            .offset(offset)
        )

        total = (await self.session.execute(count_stmt)).scalar_one()
        items = list((await self.session.execute(stmt)).scalars().all())
        return items, total
