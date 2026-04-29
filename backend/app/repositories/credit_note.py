"""Repository for Credit Note (Window 12)."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.enums import CreditNoteStatus
from app.models.invoice import CreditNote, CreditNoteLine
from app.repositories.base import BaseRepository


class CreditNoteRepository(BaseRepository[CreditNote]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(CreditNote, session)

    async def get_detail(self, org_id: int, cn_id: int) -> Optional[CreditNote]:
        stmt = (
            select(CreditNote)
            .where(
                CreditNote.id == cn_id,
                CreditNote.organization_id == org_id,
                CreditNote.deleted_at.is_(None),
            )
            .options(
                selectinload(CreditNote.lines).selectinload(CreditNoteLine.sku),
                selectinload(CreditNote.lines).selectinload(CreditNoteLine.uom),
                selectinload(CreditNote.lines).selectinload(CreditNoteLine.invoice_line),
                selectinload(CreditNote.invoice),
                selectinload(CreditNote.customer),
                selectinload(CreditNote.organization),
            )
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_with_filters(
        self,
        org_id: int,
        *,
        status: Optional[CreditNoteStatus] = None,
        invoice_id: Optional[int] = None,
        customer_id: Optional[int] = None,
        search: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[CreditNote], int]:
        filters = [
            CreditNote.organization_id == org_id,
            CreditNote.deleted_at.is_(None),
        ]
        if status is not None:
            filters.append(CreditNote.status == status)
        if invoice_id is not None:
            filters.append(CreditNote.invoice_id == invoice_id)
        if customer_id is not None:
            filters.append(CreditNote.customer_id == customer_id)
        if search:
            like = f"%{search}%"
            filters.append(
                or_(
                    CreditNote.document_no.ilike(like),
                    CreditNote.uin.ilike(like),
                    CreditNote.remarks.ilike(like),
                )
            )

        where_clause = and_(*filters)
        count_stmt = select(func.count()).select_from(CreditNote).where(where_clause)
        stmt = (
            select(CreditNote)
            .where(where_clause)
            .options(
                selectinload(CreditNote.invoice),
                selectinload(CreditNote.customer),
            )
            .order_by(CreditNote.business_date.desc(), CreditNote.id.desc())
            .limit(limit)
            .offset(offset)
        )
        total = (await self.session.execute(count_stmt)).scalar_one()
        items = list((await self.session.execute(stmt)).scalars().all())
        return items, total

    async def sum_credited_qty_per_invoice_line(
        self,
        invoice_id: int,
    ) -> dict[int, Decimal]:
        """Sum the qty already credited grouped by invoice_line_id, across every
        non-cancelled, non-deleted CN attached to ``invoice_id``.

        Used for the cumulative-quantity check: a customer can never be credited
        for more units than were originally billed on a given invoice line.
        """
        stmt = (
            select(CreditNoteLine.invoice_line_id, func.coalesce(func.sum(CreditNoteLine.qty), 0))
            .join(CreditNote, CreditNote.id == CreditNoteLine.credit_note_id)
            .where(
                CreditNote.invoice_id == invoice_id,
                CreditNote.deleted_at.is_(None),
                CreditNote.status != CreditNoteStatus.CANCELLED,
            )
            .group_by(CreditNoteLine.invoice_line_id)
        )
        rows = (await self.session.execute(stmt)).all()
        return {int(row[0]): Decimal(row[1]) for row in rows}
