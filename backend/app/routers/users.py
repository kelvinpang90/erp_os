"""Admin Users CRUD — list, create, update, reset password, toggle active."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_db, require_role
from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.core.security import hash_password
from app.enums import RoleCode
from app.models.organization import Role, User
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.users_admin import (
    PasswordReset,
    UserCreate,
    UserListItem,
    UserUpdate,
)

router = APIRouter()


def _to_item(u: User) -> UserListItem:
    return UserListItem(
        id=u.id,
        email=u.email,
        full_name=u.full_name,
        locale=u.locale,
        theme=u.theme,
        is_active=u.is_active,
        last_login_at=u.last_login_at,
        role_codes=[r.code for r in (u.roles or [])],
    )


async def _resolve_roles(db: AsyncSession, org_id: int, codes: list[str]) -> list[Role]:
    if not codes:
        return []
    stmt = select(Role).where(Role.organization_id == org_id, Role.code.in_(codes))
    rows = (await db.execute(stmt)).scalars().all()
    found = {r.code for r in rows}
    missing = set(codes) - found
    if missing:
        raise BusinessRuleError(
            message=f"Unknown role codes: {sorted(missing)}",
            error_code="UNKNOWN_ROLE",
        )
    return list(rows)


@router.get(
    "",
    response_model=PaginatedResponse[UserListItem],
    summary="List users (Admin)",
)
async def list_users(
    pagination: PaginationParams = Depends(),
    q: str | None = Query(default=None, description="Email / full_name substring"),
    include_inactive: bool = Query(default=True),
    user: User = Depends(require_role(RoleCode.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[UserListItem]:
    base = select(User).where(
        User.organization_id == user.organization_id, User.deleted_at.is_(None)
    )
    if not include_inactive:
        base = base.where(User.is_active.is_(True))
    if q:
        like = f"%{q}%"
        base = base.where((User.email.ilike(like)) | (User.full_name.ilike(like)))

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    page_stmt = (
        base.options(selectinload(User.roles))
        .order_by(User.id.desc())
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    rows = (await db.execute(page_stmt)).scalars().all()
    return PaginatedResponse.build(
        items=[_to_item(u) for u in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.post(
    "",
    response_model=UserListItem,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user (Admin)",
)
async def create_user(
    payload: UserCreate,
    user: User = Depends(require_role(RoleCode.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> UserListItem:
    org_id = user.organization_id
    existing = await db.execute(
        select(User.id).where(
            User.organization_id == org_id,
            User.email == payload.email,
            User.deleted_at.is_(None),
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ConflictError(
            message="A user with this email already exists.",
            error_code="USER_EMAIL_DUPLICATE",
        )

    roles = await _resolve_roles(db, org_id, payload.role_codes)
    new_user = User(
        organization_id=org_id,
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        locale=payload.locale,
        theme=payload.theme,
        is_active=True,
    )
    new_user.roles = roles
    db.add(new_user)
    await db.flush()
    # Reload with roles for response
    fresh = (
        await db.execute(
            select(User).options(selectinload(User.roles)).where(User.id == new_user.id)
        )
    ).scalar_one()
    return _to_item(fresh)


async def _get_user_or_404(db: AsyncSession, org_id: int, user_id: int) -> User:
    stmt = (
        select(User)
        .options(selectinload(User.roles))
        .where(
            User.id == user_id,
            User.organization_id == org_id,
            User.deleted_at.is_(None),
        )
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise NotFoundError(message=f"User {user_id} not found.")
    return row


@router.get("/{user_id}", response_model=UserListItem, summary="Get a user")
async def get_user(
    user_id: int,
    user: User = Depends(require_role(RoleCode.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> UserListItem:
    target = await _get_user_or_404(db, user.organization_id, user_id)
    return _to_item(target)


@router.patch("/{user_id}", response_model=UserListItem, summary="Update a user")
async def update_user(
    user_id: int,
    payload: UserUpdate,
    user: User = Depends(require_role(RoleCode.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> UserListItem:
    target = await _get_user_or_404(db, user.organization_id, user_id)
    if payload.full_name is not None:
        target.full_name = payload.full_name
    if payload.locale is not None:
        target.locale = payload.locale
    if payload.theme is not None:
        target.theme = payload.theme
    if payload.is_active is not None:
        if target.id == user.id and payload.is_active is False:
            raise BusinessRuleError(
                message="You cannot deactivate your own account.",
                error_code="CANNOT_DEACTIVATE_SELF",
            )
        target.is_active = payload.is_active
    if payload.role_codes is not None:
        target.roles = await _resolve_roles(db, user.organization_id, payload.role_codes)
    db.add(target)
    await db.flush()
    return _to_item(target)


@router.post(
    "/{user_id}/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Admin password reset",
)
async def reset_password(
    user_id: int,
    payload: PasswordReset,
    user: User = Depends(require_role(RoleCode.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> None:
    target = await _get_user_or_404(db, user.organization_id, user_id)
    target.password_hash = hash_password(payload.new_password)
    target.locked_until = None  # clear any lockout when admin resets
    db.add(target)
    await db.flush()


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a user",
)
async def soft_delete(
    user_id: int,
    user: User = Depends(require_role(RoleCode.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> None:
    target = await _get_user_or_404(db, user.organization_id, user_id)
    if target.id == user.id:
        raise BusinessRuleError(
            message="You cannot delete your own account.",
            error_code="CANNOT_DELETE_SELF",
        )
    target.deleted_at = datetime.now(UTC).replace(tzinfo=None)
    target.is_active = False
    db.add(target)
    await db.flush()
