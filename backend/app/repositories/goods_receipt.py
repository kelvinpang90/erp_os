"""Repository for GoodsReceipt (Window 8)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.purchase import GoodsReceipt, GoodsReceiptLine
from app.repositories.base import BaseRepository


class GoodsReceiptRepository(BaseRepository[GoodsReceipt]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(GoodsReceipt, session)

    async def get_detail(self, org_id: int, gr_id: int) -> Optional[GoodsReceipt]:
        stmt = (
            select(GoodsReceipt)
            .where(
                GoodsReceipt.id == gr_id,
                GoodsReceipt.organization_id == org_id,
                GoodsReceipt.deleted_at.is_(None),
            )
            .options(
                selectinload(GoodsReceipt.lines).selectinload(GoodsReceiptLine.sku),
                selectinload(GoodsReceipt.lines).selectinload(GoodsReceiptLine.purchase_order_line),
                selectinload(GoodsReceipt.purchase_order),
                selectinload(GoodsReceipt.warehouse),
                selectinload(GoodsReceipt.receiver),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_document_no(self, org_id: int, document_no: str) -> Optional[GoodsReceipt]:
        stmt = select(GoodsReceipt).where(
            GoodsReceipt.organization_id == org_id,
            GoodsReceipt.document_no == document_no,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_with_filters(
        self,
        org_id: int,
        *,
        purchase_order_id: Optional[int] = None,
        warehouse_id: Optional[int] = None,
        search: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[GoodsReceipt], int]:
        filters = [
            GoodsReceipt.organization_id == org_id,
            GoodsReceipt.deleted_at.is_(None),
        ]
        if purchase_order_id is not None:
            filters.append(GoodsReceipt.purchase_order_id == purchase_order_id)
        if warehouse_id is not None:
            filters.append(GoodsReceipt.warehouse_id == warehouse_id)
        if search:
            like = f"%{search}%"
            filters.append(
                or_(
                    GoodsReceipt.document_no.ilike(like),
                    GoodsReceipt.delivery_note_no.ilike(like),
                    GoodsReceipt.remarks.ilike(like),
                )
            )

        where_clause = and_(*filters)
        count_stmt = select(func.count()).select_from(GoodsReceipt).where(where_clause)
        stmt = (
            select(GoodsReceipt)
            .where(where_clause)
            .options(selectinload(GoodsReceipt.purchase_order))
            .order_by(GoodsReceipt.receipt_date.desc(), GoodsReceipt.id.desc())
            .limit(limit)
            .offset(offset)
        )

        total = (await self.session.execute(count_stmt)).scalar_one()
        items = list((await self.session.execute(stmt)).scalars().all())
        return items, total
