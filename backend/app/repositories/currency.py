from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.master import Currency
from app.repositories.base import BaseRepository


class CurrencyRepository(BaseRepository[Currency]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Currency, session)

    async def get_by_code(self, code: str) -> Currency | None:
        return await self.session.get(Currency, code)

    async def list_active(self) -> list[Currency]:
        stmt = select(Currency).where(Currency.is_active == True)  # noqa: E712
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
