"""
FastAPI dependency injection functions.

Usage in routers:
    @router.get("/me")
    async def me(user: User = Depends(get_current_user)):
        ...

    @router.delete("/foo")
    async def delete_foo(user: User = Depends(require_role(RoleCode.ADMIN))):
        ...
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Callable

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.exceptions import AuthorizationError
from app.core.security import decode_access_token
from app.enums import RoleCode
from app.models.organization import User
from app.repositories.user import UserRepository

# OAuth2 scheme — just extracts Bearer token from Authorization header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


# ── Database session ──────────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a fresh AsyncSession per request, auto-commit on success."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Current user ──────────────────────────────────────────────────────────────

async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Decode the Bearer token and return the authenticated User.

    Raises:
        AuthenticationError: Token missing, expired, or invalid; user inactive / deleted.
    """
    from app.core.exceptions import AuthenticationError

    if not token:
        raise AuthenticationError(
            message="Authentication credentials were not provided.",
            error_code="AUTHENTICATION_REQUIRED",
        )

    payload = decode_access_token(token)

    repo = UserRepository(db)
    user = await repo.get_with_roles_permissions(payload.user_id)

    if user is None or not user.is_active or user.deleted_at is not None:
        raise AuthenticationError(
            message="User account is inactive or does not exist.",
            error_code="ACCOUNT_INACTIVE",
        )

    # Organization guard — ensures token was issued for the same org
    if user.organization_id != payload.org_id:
        raise AuthenticationError(error_code="TOKEN_INVALID")

    return user


# ── Role-based access control ─────────────────────────────────────────────────

def require_role(*role_codes: RoleCode) -> Callable:
    """
    Return a dependency that ensures the current user holds at least one of the
    specified roles.

    Usage:
        Depends(require_role(RoleCode.ADMIN, RoleCode.MANAGER))
    """

    async def _dependency(user: User = Depends(get_current_user)) -> User:
        user_roles = {r.code for r in user.roles} if user.roles else set()
        required = {r.value for r in role_codes}
        if not user_roles & required:
            raise AuthorizationError(
                message=(
                    f"This action requires one of the following roles: "
                    f"{', '.join(required)}"
                ),
            )
        return user

    return _dependency


# ── Convenience shortcut ──────────────────────────────────────────────────────

async def get_current_org_id(
    user: User = Depends(get_current_user),
) -> int:
    """Return the organization_id of the currently authenticated user."""
    return user.organization_id
