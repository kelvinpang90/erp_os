# NOTE: do NOT add "from __future__ import annotations" here — breaks slowapi Body() injection
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_role
from app.enums import InvoiceStatus, RoleCode
from app.models.organization import User
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.invoice import (
    ConsolidatedScanResult,
    FinalizeScanResult,
    GenerateConsolidatedIn,
    GenerateFromSOIn,
    InvoiceDetail,
    InvoiceListItem,
    RejectByBuyerIn,
)
from app.services import einvoice as einvoice_service
from app.services import einvoice_precheck as einvoice_precheck_service

router = APIRouter()

_READ_ROLES = [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.SALES]
_WRITE_ROLES = [RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.SALES]
# Buyer rejection in this demo is gated to Manager/Admin (acting on the
# buyer's behalf via the back office) — Sales cannot reject their own invoices.
_REJECT_ROLES = [RoleCode.ADMIN, RoleCode.MANAGER]
_ADMIN_ROLES = [RoleCode.ADMIN, RoleCode.MANAGER]


# ── Generate-from-SO (mounted on the invoice router for cohesion) ────────────


@router.post(
    "/generate-from-so/{so_id}",
    response_model=InvoiceDetail,
    status_code=status.HTTP_201_CREATED,
)
async def generate_from_so(
    so_id: int,
    data: GenerateFromSOIn = GenerateFromSOIn(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_WRITE_ROLES)),
) -> InvoiceDetail:
    return await einvoice_service.generate_draft_from_so(
        db, so_id=so_id, org_id=user.organization_id, user=user, payload=data
    )


# ── Admin endpoints first to avoid /{id} route shadowing ─────────────────────


@router.post(
    "/admin/run-finalize-scan",
    response_model=FinalizeScanResult,
)
async def run_finalize_scan(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_ADMIN_ROLES)),
) -> FinalizeScanResult:
    return await einvoice_service.run_finalize_scan(
        db, org_id=user.organization_id, user=user
    )


@router.post(
    "/admin/generate-monthly-consolidated",
    response_model=ConsolidatedScanResult,
)
async def generate_monthly_consolidated(
    data: GenerateConsolidatedIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_ADMIN_ROLES)),
) -> ConsolidatedScanResult:
    """Roll up the month's B2C-customer shipped Sales Orders into one
    Consolidated Invoice per customer (DRAFT)."""
    return await einvoice_service.generate_monthly_consolidated(
        db,
        org_id=user.organization_id,
        user=user,
        year=data.year,
        month=data.month,
    )


# ── List / detail ─────────────────────────────────────────────────────────────


@router.get("", response_model=PaginatedResponse[InvoiceListItem])
async def list_invoices(
    status_: Optional[InvoiceStatus] = Query(None, alias="status"),
    customer_id: Optional[int] = Query(None),
    sales_order_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_READ_ROLES)),
) -> PaginatedResponse[InvoiceListItem]:
    return await einvoice_service.list_invoices(
        db,
        pagination,
        org_id=user.organization_id,
        status=status_,
        customer_id=customer_id,
        sales_order_id=sales_order_id,
        search=search,
    )


@router.get("/{invoice_id}", response_model=InvoiceDetail)
async def get_invoice(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_READ_ROLES)),
) -> InvoiceDetail:
    return await einvoice_service.get_invoice(
        db, invoice_id, org_id=user.organization_id, user=user
    )


# ── State transitions ────────────────────────────────────────────────────────


@router.post("/{invoice_id}/precheck", response_model=InvoiceDetail)
async def precheck_invoice(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_WRITE_ROLES)),
) -> InvoiceDetail:
    """Run the 10-item compliance checklist (7 hard + 3 LLM-soft) and persist
    the result on the invoice. Frontend renders the checklist Modal off the
    returned ``precheck_result``."""
    return await einvoice_precheck_service.precheck_invoice(
        db, invoice_id=invoice_id, org_id=user.organization_id, user=user
    )


@router.post("/{invoice_id}/submit", response_model=InvoiceDetail)
async def submit_invoice(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_WRITE_ROLES)),
) -> InvoiceDetail:
    return await einvoice_service.submit_to_myinvois(
        db, invoice_id=invoice_id, org_id=user.organization_id, user=user
    )


@router.post("/{invoice_id}/reject", response_model=InvoiceDetail)
async def reject_invoice(
    invoice_id: int,
    data: RejectByBuyerIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*_REJECT_ROLES)),
) -> InvoiceDetail:
    return await einvoice_service.reject_by_buyer(
        db, invoice_id=invoice_id, org_id=user.organization_id, user=user, payload=data
    )
