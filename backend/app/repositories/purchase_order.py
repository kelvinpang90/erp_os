from __future__ import annotations

from typing import Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.enums import POStatus
from app.models.purchase import PurchaseOrder, PurchaseOrderLine
from app.repositories.base import BaseRepository


class PurchaseOrderRepository(BaseRepository[PurchaseOrder]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(PurchaseOrder, session)

    async def get_detail(self, org_id: int, po_id: int) -> Optional[PurchaseOrder]:
        stmt = (
            select(PurchaseOrder)
            .where(
                PurchaseOrder.id == po_id,
                PurchaseOrder.organization_id == org_id,
                PurchaseOrder.deleted_at.is_(None),
            )
            .options(selectinload(PurchaseOrder.lines).selectinload(PurchaseOrderLine.sku))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_document_no(self, org_id: int, document_no: str) -> Optional[PurchaseOrder]:
        stmt = select(PurchaseOrder).where(
            PurchaseOrder.organization_id == org_id,
            PurchaseOrder.document_no == document_no,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_with_filters(
        self,
        org_id: int,
        *,
        status: Optional[POStatus] = None,
        supplier_id: Optional[int] = None,
        warehouse_id: Optional[int] = None,
        search: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[PurchaseOrder], int]:
        filters = [
            PurchaseOrder.organization_id == org_id,
            PurchaseOrder.deleted_at.is_(None),
        ]
        if status is not None:
            filters.append(PurchaseOrder.status == status)
        if supplier_id is not None:
            filters.append(PurchaseOrder.supplier_id == supplier_id)
        if warehouse_id is not None:
            filters.append(PurchaseOrder.warehouse_id == warehouse_id)
        if search:
            like = f"%{search}%"
            filters.append(
                or_(
                    PurchaseOrder.document_no.ilike(like),
                    PurchaseOrder.remarks.ilike(like),
                )
            )

        where_clause = and_(*filters)
        count_stmt = select(func.count()).select_from(PurchaseOrder).where(where_clause)
        stmt = (
            select(PurchaseOrder)
            .where(where_clause)
            .order_by(PurchaseOrder.business_date.desc(), PurchaseOrder.id.desc())
            .limit(limit)
            .offset(offset)
        )

        total = (await self.session.execute(count_stmt)).scalar_one()
        items = list((await self.session.execute(stmt)).scalars().all())
        return items, total
