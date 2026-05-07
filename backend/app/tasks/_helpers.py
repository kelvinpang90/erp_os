"""Shared helpers for Celery tasks (sync ↔ async bridge utilities)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import RoleCode
from app.models.organization import Role, User


async def get_system_user_for_org(
    session: AsyncSession, org_id: int
) -> Optional[User]:
    """Pick a representative actor user for system-triggered actions.

    Strategy: first active ADMIN user in the org. Returns None if none exists,
    so callers can decide whether to skip or hard-fail.
    """
    stmt = (
        select(User)
        .join(User.roles)
        .where(
            User.organization_id == org_id,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
            Role.code == RoleCode.ADMIN.value,
        )
        .order_by(User.id.asc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
