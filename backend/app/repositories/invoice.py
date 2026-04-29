"""Repository for Invoice (Window 11)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.enums import InvoiceStatus
from app.models.invoice import Invoice, InvoiceLine
from app.repositories.base import BaseRepository


class InvoiceRepository(BaseRepository[Invoice]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Invoice, session)

    async def get_detail(self, org_id: int, invoice_id: int) -> Optional[Invoice]:
        stmt = (
            select(Invoice)
            .where(
                Invoice.id == invoice_id,
                Invoice.organization_id == org_id,
                Invoice.deleted_at.is_(None),
            )
            .options(
                selectinload(Invoice.lines).selectinload(InvoiceLine.sku),
                selectinload(Invoice.lines).selectinload(InvoiceLine.uom),
                selectinload(Invoice.lines).selectinload(InvoiceLine.tax_rate),
                selectinload(Invoice.customer),
                selectinload(Invoice.warehouse),
                selectinload(Invoice.sales_order),
                selectinload(Invoice.organization),
            )
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_so_id(self, org_id: int, sales_order_id: int) -> Optional[Invoice]:
        """Idempotency check — returns existing invoice for an SO if any."""
        stmt = select(Invoice).where(
            Invoice.organization_id == org_id,
            Invoice.sales_order_id == sales_order_id,
            Invoice.deleted_at.is_(None),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_with_filters(
        self,
        org_id: int,
        *,
        status: Optional[InvoiceStatus] = None,
        customer_id: Optional[int] = None,
        sales_order_id: Optional[int] = None,
        search: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Invoice], int]:
        filters = [
            Invoice.organization_id == org_id,
            Invoice.deleted_at.is_(None),
        ]
        if status is not None:
            filters.append(Invoice.status == status)
        if customer_id is not None:
            filters.append(Invoice.customer_id == customer_id)
        if sales_order_id is not None:
            filters.append(Invoice.sales_order_id == sales_order_id)
        if search:
            like = f"%{search}%"
            filters.append(
                or_(
                    Invoice.document_no.ilike(like),
                    Invoice.uin.ilike(like),
                    Invoice.remarks.ilike(like),
                )
            )

        where_clause = and_(*filters)
        count_stmt = select(func.count()).select_from(Invoice).where(where_clause)
        stmt = (
            select(Invoice)
            .where(where_clause)
            .options(
                selectinload(Invoice.customer),
                selectinload(Invoice.sales_order),
            )
            .order_by(Invoice.business_date.desc(), Invoice.id.desc())
            .limit(limit)
            .offset(offset)
        )

        total = (await self.session.execute(count_stmt)).scalar_one()
        items = list((await self.session.execute(stmt)).scalars().all())
        return items, total

    async def find_finalizable(
        self,
        org_id: int,
        *,
        cutoff: datetime,
    ) -> list[Invoice]:
        """VALIDATED invoices whose validated_at < cutoff and not yet finalized."""
        stmt = select(Invoice).where(
            Invoice.organization_id == org_id,
            Invoice.deleted_at.is_(None),
            Invoice.status == InvoiceStatus.VALIDATED,
            Invoice.validated_at.is_not(None),
            Invoice.validated_at < cutoff,
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def bulk_finalize(
        self,
        org_id: int,
        *,
        cutoff: datetime,
        now: datetime,
    ) -> int:
        """Atomic bulk transition VALIDATED -> FINAL for all expired invoices.

        Returns the number of rows updated.
        """
        stmt = (
            update(Invoice)
            .where(
                Invoice.organization_id == org_id,
                Invoice.deleted_at.is_(None),
                Invoice.status == InvoiceStatus.VALIDATED,
                Invoice.validated_at.is_not(None),
                Invoice.validated_at < cutoff,
            )
            .values(status=InvoiceStatus.FINAL, finalized_at=now)
            .execution_options(synchronize_session=False)
        )
        result = await self.session.execute(stmt)
        return result.rowcount or 0
