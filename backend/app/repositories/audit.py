"""Read-only repository for audit_logs (admin viewer)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.enums import AuditAction
from app.models.audit import AuditLog
from app.models.organization import User


class AuditLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_paged(
        self,
        org_id: int,
        *,
        offset: int,
        limit: int,
        entity_type: str | None = None,
        entity_id: int | None = None,
        actor_user_id: int | None = None,
        action: AuditAction | None = None,
    ) -> tuple[list[AuditLog], int]:
        base = select(AuditLog).where(AuditLog.organization_id == org_id)
        if entity_type:
            base = base.where(AuditLog.entity_type == entity_type)
        if entity_id is not None:
            base = base.where(AuditLog.entity_id == entity_id)
        if actor_user_id is not None:
            base = base.where(AuditLog.actor_user_id == actor_user_id)
        if action is not None:
            base = base.where(AuditLog.action == action)

        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()

        page_stmt = (
            base.options(selectinload(AuditLog.actor))
            .order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = (await self.session.execute(page_stmt)).scalars().all()
        return list(rows), int(total)

    async def get_user_emails(self, user_ids: list[int]) -> dict[int, str]:
        if not user_ids:
            return {}
        stmt = select(User.id, User.email).where(User.id.in_(user_ids))
        return dict((await self.session.execute(stmt)).all())
