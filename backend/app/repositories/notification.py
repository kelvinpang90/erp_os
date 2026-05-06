"""Notification repository — list / count / mark read."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import Notification


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class NotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _scope_filter(self, org_id: int, user_id: int, role_codes: set[str]):
        # User sees: notifications targeted at their user_id OR any role they hold,
        # OR org-wide (target_user_id IS NULL AND target_role IS NULL).
        clauses = [Notification.target_user_id == user_id]
        if role_codes:
            clauses.append(Notification.target_role.in_(role_codes))
        clauses.append(
            and_(
                Notification.target_user_id.is_(None),
                Notification.target_role.is_(None),
            )
        )
        return and_(
            Notification.organization_id == org_id,
            or_(*clauses),
        )

    async def list_paged(
        self,
        org_id: int,
        user_id: int,
        role_codes: set[str],
        *,
        offset: int,
        limit: int,
        unread_only: bool = False,
    ) -> tuple[list[Notification], int]:
        scope = self._scope_filter(org_id, user_id, role_codes)
        base = select(Notification).where(scope)
        if unread_only:
            base = base.where(Notification.is_read.is_(False))

        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()

        page_stmt = (
            base.order_by(Notification.created_at.desc(), Notification.id.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = (await self.session.execute(page_stmt)).scalars().all()
        return list(rows), int(total)

    async def unread_count(self, org_id: int, user_id: int, role_codes: set[str]) -> int:
        scope = self._scope_filter(org_id, user_id, role_codes)
        stmt = (
            select(func.count())
            .select_from(Notification)
            .where(scope, Notification.is_read.is_(False))
        )
        return int((await self.session.execute(stmt)).scalar_one())

    async def mark_one_read(
        self, org_id: int, user_id: int, role_codes: set[str], notif_id: int
    ) -> int:
        scope = self._scope_filter(org_id, user_id, role_codes)
        stmt = (
            update(Notification)
            .where(scope, Notification.id == notif_id, Notification.is_read.is_(False))
            .values(is_read=True, read_at=_now())
        )
        result = await self.session.execute(stmt)
        return int(result.rowcount or 0)

    async def mark_all_read(
        self, org_id: int, user_id: int, role_codes: set[str]
    ) -> int:
        scope = self._scope_filter(org_id, user_id, role_codes)
        stmt = (
            update(Notification)
            .where(scope, Notification.is_read.is_(False))
            .values(is_read=True, read_at=_now())
        )
        result = await self.session.execute(stmt)
        return int(result.rowcount or 0)
