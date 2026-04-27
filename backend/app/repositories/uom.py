from __future__ import annotations

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.master import UOM
from app.repositories.base import BaseRepository


class UOMRepository(BaseRepository[UOM]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(UOM, session)

    async def get_by_code(self, org_id: int, code: str) -> UOM | None:
        stmt = select(UOM).where(
            and_(
                UOM.organization_id == org_id,
                UOM.code == code,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
