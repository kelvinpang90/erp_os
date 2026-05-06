"""Notification endpoints — list / count / mark read.

Scope: each call returns notifications targeted at the current user, any
role they hold, or org-wide broadcasts. No cross-user reads.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.exceptions import NotFoundError
from app.models.organization import User
from app.repositories.notification import NotificationRepository
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.notification import NotificationResponse, UnreadCountResponse

router = APIRouter()


def _user_role_codes(user: User) -> set[str]:
    return {r.code for r in (user.roles or [])}


@router.get(
    "",
    response_model=PaginatedResponse[NotificationResponse],
    summary="List notifications visible to current user",
)
async def list_notifications(
    pagination: PaginationParams = Depends(),
    unread_only: bool = Query(default=False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[NotificationResponse]:
    repo = NotificationRepository(db)
    rows, total = await repo.list_paged(
        user.organization_id,
        user.id,
        _user_role_codes(user),
        offset=pagination.offset,
        limit=pagination.limit,
        unread_only=unread_only,
    )
    return PaginatedResponse.build(
        items=[NotificationResponse.model_validate(r) for r in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
    summary="Unread notification count for current user",
)
async def unread_count(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UnreadCountResponse:
    repo = NotificationRepository(db)
    n = await repo.unread_count(user.organization_id, user.id, _user_role_codes(user))
    return UnreadCountResponse(unread=n)


@router.post(
    "/{notification_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def mark_read(
    notification_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = NotificationRepository(db)
    updated = await repo.mark_one_read(
        user.organization_id, user.id, _user_role_codes(user), notification_id
    )
    if updated == 0:
        # Either it doesn't exist, isn't visible to this user, or already read.
        raise NotFoundError(message=f"Notification {notification_id} not found.")


@router.post(
    "/read-all",
    summary="Mark all visible unread notifications as read",
)
async def mark_all_read(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    repo = NotificationRepository(db)
    n = await repo.mark_all_read(user.organization_id, user.id, _user_role_codes(user))
    return {"updated": n}
