"""Audit log read endpoints — Admin only."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_role
from app.enums import AuditAction, RoleCode
from app.models.organization import User
from app.repositories.audit import AuditLogRepository
from app.schemas.audit import AuditLogResponse
from app.schemas.common import PaginatedResponse, PaginationParams

router = APIRouter()


@router.get(
    "/logs",
    response_model=PaginatedResponse[AuditLogResponse],
    summary="List audit-log entries (Admin only)",
)
async def list_audit_logs(
    pagination: PaginationParams = Depends(),
    entity_type: str | None = Query(default=None, description="e.g. PO, SO, INVOICE, CN"),
    entity_id: int | None = Query(default=None),
    actor_user_id: int | None = Query(default=None),
    action: AuditAction | None = Query(default=None),
    user: User = Depends(require_role(RoleCode.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[AuditLogResponse]:
    repo = AuditLogRepository(db)
    rows, total = await repo.list_paged(
        user.organization_id,
        offset=pagination.offset,
        limit=pagination.limit,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_user_id=actor_user_id,
        action=action,
    )
    items = [
        AuditLogResponse(
            id=r.id,
            organization_id=r.organization_id,
            entity_type=r.entity_type,
            entity_id=r.entity_id,
            action=r.action,
            actor_user_id=r.actor_user_id,
            actor_email=r.actor.email if r.actor else None,
            before=r.before,
            after=r.after,
            ip=r.ip,
            user_agent=r.user_agent,
            request_id=r.request_id,
            occurred_at=r.occurred_at,
        )
        for r in rows
    ]
    return PaginatedResponse.build(
        items=items, total=total, page=pagination.page, page_size=pagination.page_size
    )
