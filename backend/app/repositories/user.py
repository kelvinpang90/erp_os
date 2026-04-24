"""
UserRepository — data access layer for User, Role, Permission, and LoginAttempt.

Business logic belongs in services/auth.py; this file only touches the database.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.audit import LoginAttempt
from app.models.organization import Role, User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(User, session)

    # ── Lookup ────────────────────────────────────────────────────────────────

    async def get_by_email(self, org_id: int, email: str) -> User | None:
        """
        Find an active (non-deleted) user by email within an organization.
        Does NOT load roles/permissions — use get_with_roles_permissions for that.
        """
        stmt = (
            select(User)
            .where(
                and_(
                    User.organization_id == org_id,
                    User.email == email,
                    User.deleted_at.is_(None),
                )
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_roles_permissions(self, user_id: int) -> User | None:
        """
        Fetch a user with fully loaded roles and each role's permissions.
        Uses selectinload to avoid N+1.
        """
        stmt = (
            select(User)
            .where(
                and_(
                    User.id == user_id,
                    User.deleted_at.is_(None),
                )
            )
            .options(
                selectinload(User.roles).selectinload(Role.permissions)
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # ── Login attempt tracking ────────────────────────────────────────────────

    async def count_recent_failed_attempts(
        self,
        email: str,
        within_minutes: int = 5,
    ) -> int:
        """Count failed login attempts for *email* in the last *within_minutes* minutes."""
        since = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=within_minutes)
        stmt = (
            select(func.count())
            .select_from(LoginAttempt)
            .where(
                and_(
                    LoginAttempt.email == email,
                    LoginAttempt.success == False,  # noqa: E712
                    LoginAttempt.attempted_at >= since,
                )
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def record_login_attempt(
        self,
        *,
        email: str,
        success: bool,
        org_id: int | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> LoginAttempt:
        """Insert a new LoginAttempt record and flush."""
        attempt = LoginAttempt(
            email=email,
            success=success,
            ip=ip_address or "",
            user_agent=user_agent,
            attempted_at=datetime.now(UTC).replace(tzinfo=None),
        )
        self.session.add(attempt)
        await self.session.flush()
        return attempt

    # ── User mutations ────────────────────────────────────────────────────────

    async def update_last_login(
        self,
        user: User,
        ip_address: str | None,
    ) -> None:
        """Stamp last_login_at and last_login_ip, flush."""
        user.last_login_at = datetime.now(UTC).replace(tzinfo=None)
        user.last_login_ip = ip_address
        self.session.add(user)
        await self.session.flush()

    async def set_locked_until(self, user: User, until: datetime) -> None:
        """Lock the account until *until* (naive UTC datetime)."""
        user.locked_until = until
        self.session.add(user)
        await self.session.flush()
