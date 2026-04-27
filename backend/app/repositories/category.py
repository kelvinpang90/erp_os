from __future__ import annotations

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.master import Category
from app.repositories.base import BaseRepository


class CategoryRepository(BaseRepository[Category]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Category, session)

    async def get_by_code(self, org_id: int, code: str) -> Category | None:
        stmt = select(Category).where(
            and_(
                Category.organization_id == org_id,
                Category.code == code,
                Category.deleted_at.is_(None),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_children(self, org_id: int, parent_id: int) -> list[Category]:
        stmt = select(Category).where(
            and_(
                Category.organization_id == org_id,
                Category.parent_id == parent_id,
                Category.deleted_at.is_(None),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
