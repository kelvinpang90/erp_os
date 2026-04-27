from __future__ import annotations

from datetime import date

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.master import ExchangeRate
from app.repositories.base import BaseRepository


class ExchangeRateRepository(BaseRepository[ExchangeRate]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ExchangeRate, session)

    async def get_rate(
        self,
        org_id: int,
        from_currency: str,
        to_currency: str,
        on_date: date | None = None,
    ) -> ExchangeRate | None:
        """Get the most recent rate effective on or before a given date."""
        target_date = on_date or date.today()
        stmt = (
            select(ExchangeRate)
            .where(
                and_(
                    ExchangeRate.organization_id == org_id,
                    ExchangeRate.from_currency == from_currency,
                    ExchangeRate.to_currency == to_currency,
                    ExchangeRate.effective_from <= target_date,
                )
            )
            .order_by(ExchangeRate.effective_from.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
