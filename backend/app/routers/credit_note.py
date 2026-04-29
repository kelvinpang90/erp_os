# NOTE: do NOT add "from __future__ import annotations" here — breaks slowapi Body() injection
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_role
from app.enums import CreditNoteStatus, RoleCode
from app.models.organization import User
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.credit_note import (
    CreditNoteCreateIn,
    CreditNoteDetail,
    CreditNoteListItem,
)
from app.services import credit_note as credit_note_service

router = APIRouter()

_READ_ROLES = [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.SALES]
_WRITE_ROLES = [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.SALES]
_CANCEL_ROLES = [RoleCode.ADMIN, RoleCode.MANAGER]


@router.get("", response_model=PaginatedResponse[CreditNoteListItem])
async def list_credit_notes(
    status_: Optional[CreditNoteStatus] = Query(None, alias="status"),
    invoice_id: Optional[int] = Query(None),
    customer_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_READ_ROLES)),
) -> PaginatedResponse[CreditNoteListItem]:
    return await credit_note_service.list_credit_notes(
        db,
        pagination,
        org_id=user.organization_id,
        status=status_,
        invoice_id=invoice_id,
        customer_id=customer_id,
        search=search,
    )


@router.get("/{cn_id}", response_model=CreditNoteDetail)
async def get_credit_note(
    cn_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_READ_ROLES)),
) -> CreditNoteDetail:
    return await credit_note_service.get_credit_note(
        db, cn_id, org_id=user.organization_id
    )


@router.post(
    "",
    response_model=CreditNoteDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_credit_note(
    data: CreditNoteCreateIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_WRITE_ROLES)),
) -> CreditNoteDetail:
    return await credit_note_service.create_credit_note(
        db, org_id=user.organization_id, user=user, payload=data
    )


@router.post("/{cn_id}/submit", response_model=CreditNoteDetail)
async def submit_credit_note(
    cn_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_WRITE_ROLES)),
) -> CreditNoteDetail:
    return await credit_note_service.submit_credit_note_to_myinvois(
        db, cn_id=cn_id, org_id=user.organization_id, user=user
    )


@router.post("/{cn_id}/cancel", response_model=CreditNoteDetail)
async def cancel_credit_note(
    cn_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_CANCEL_ROLES)),
) -> CreditNoteDetail:
    return await credit_note_service.cancel_credit_note(
        db, cn_id=cn_id, org_id=user.organization_id, user=user
    )
