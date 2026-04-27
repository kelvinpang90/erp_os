from __future__ import annotations

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.master import TaxRate
from app.repositories.base import BaseRepository


class TaxRateRepository(BaseRepository[TaxRate]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(TaxRate, session)

    async def get_by_code(self, org_id: int, code: str) -> TaxRate | None:
        stmt = select(TaxRate).where(
            and_(
                TaxRate.organization_id == org_id,
                TaxRate.code == code,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_default(self, org_id: int) -> TaxRate | None:
        stmt = select(TaxRate).where(
            and_(
                TaxRate.organization_id == org_id,
                TaxRate.is_default == True,  # noqa: E712
                TaxRate.is_active == True,  # noqa: E712
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def clear_default(self, org_id: int) -> None:
        """Clear is_default flag on all tax rates for an org before setting a new default."""
        from sqlalchemy import update
        stmt = (
            update(TaxRate)
            .where(TaxRate.organization_id == org_id)
            .values(is_default=False)
        )
        await self.session.execute(stmt)
