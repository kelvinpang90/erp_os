from __future__ import annotations

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.master import Brand
from app.repositories.base import BaseRepository


class BrandRepository(BaseRepository[Brand]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Brand, session)

    async def get_by_code(self, org_id: int, code: str) -> Brand | None:
        stmt = select(Brand).where(
            and_(
                Brand.organization_id == org_id,
                Brand.code == code,
                Brand.deleted_at.is_(None),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
