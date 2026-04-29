"""e-Invoice service — Window 11.

Covers:
- ``generate_draft_from_so`` — build an Invoice DRAFT from a shipped SalesOrder.
  Window 11 enforces 1 SO ↔ 1 Invoice; partial-invoicing across multiple
  shipments is a Window 12 follow-up.
- ``submit_to_myinvois`` — call the configured adapter, transition
  DRAFT → VALIDATED, persist UIN/QR, publish ``DocumentStatusChanged`` and
  ``EInvoiceValidated`` (the latter triggers the buyer-notification handler
  registered in ``app.events.registry``).
- ``reject_by_buyer`` — VALIDATED → REJECTED within the 72h opposition
  window (72s in DEMO_MODE).
- ``_lazy_finalize_if_due`` — on every read, opportunistically advance
  VALIDATED → FINAL once the window has elapsed. No background scheduler
  required for the demo; an admin scan endpoint complements this for bulk
  finalisation.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    BusinessRuleError,
    InvalidStatusTransitionError,
    NotFoundError,
)
from app.enums import InvoiceStatus, InvoiceType, RejectedBy, SOStatus
from app.events import event_bus
from app.events.types import DocumentStatusChanged, EInvoiceValidated
from app.integrations.myinvois import InvoicePayload
from app.integrations.myinvois_factory import get_myinvois_adapter
from app.models.invoice import Invoice, InvoiceLine
from app.models.organization import User
from app.models.sales import SalesOrder
from app.repositories.invoice import InvoiceRepository
from app.repositories.sales_order import SalesOrderRepository
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.invoice import (
    FinalizeScanResult,
    GenerateFromSOIn,
    InvoiceDetail,
    InvoiceLineResponse,
    InvoiceListItem,
    RejectByBuyerIn,
)
from app.services.sequence import next_document_no

logger = structlog.get_logger()

_FOUR = Decimal("0.0001")


# ── DEMO_MODE timer helper ───────────────────────────────────────────────────


def get_finalize_window() -> timedelta:
    """72 seconds in demo mode, 72 hours in production."""
    return (
        timedelta(seconds=72) if settings.DEMO_MODE else timedelta(hours=72)
    )


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _quantize(v: Decimal) -> Decimal:
    return v.quantize(_FOUR, rounding=ROUND_HALF_UP)


# ── Mappers ──────────────────────────────────────────────────────────────────


def _annotate_window(detail: InvoiceDetail, invoice: Invoice) -> InvoiceDetail:
    window = get_finalize_window()
    detail.finalize_window_seconds = int(window.total_seconds())
    if invoice.status == InvoiceStatus.VALIDATED and invoice.validated_at:
        elapsed = (_now() - invoice.validated_at).total_seconds()
        remaining = int(window.total_seconds() - elapsed)
        detail.seconds_until_finalize = max(remaining, 0)
    return detail


def _to_list_item(invoice: Invoice) -> InvoiceListItem:
    item = InvoiceListItem.model_validate(invoice)
    if invoice.sales_order is not None:
        item.sales_order_no = invoice.sales_order.document_no
    if invoice.customer is not None:
        item.customer_name = invoice.customer.name
    return item


def _to_detail(invoice: Invoice) -> InvoiceDetail:
    detail = InvoiceDetail.model_validate(invoice)
    if invoice.sales_order is not None:
        detail.sales_order_no = invoice.sales_order.document_no
    if invoice.customer is not None:
        detail.customer_name = invoice.customer.name
    if invoice.warehouse is not None:
        detail.warehouse_name = invoice.warehouse.name

    line_resps: list[InvoiceLineResponse] = []
    for ln in invoice.lines or []:
        resp = InvoiceLineResponse.model_validate(ln)
        if ln.sku is not None:
            resp.sku_code = ln.sku.code
            resp.sku_name = ln.sku.name
        if ln.uom is not None:
            resp.uom_code = ln.uom.code
        line_resps.append(resp)
    detail.lines = line_resps
    return _annotate_window(detail, invoice)


# ── Internal helpers ─────────────────────────────────────────────────────────


def _assert_status(invoice: Invoice, allowed: set[InvoiceStatus], action: str) -> None:
    if invoice.status not in allowed:
        raise InvalidStatusTransitionError(
            message=(
                f"Cannot {action} invoice {invoice.document_no}: "
                f"current status is {invoice.status.value}, "
                f"expected one of {sorted(s.value for s in allowed)}."
            ),
            error_code="INVOICE_INVALID_STATUS",
        )


def _build_payload(
    invoice: Invoice,
) -> InvoicePayload:
    org = invoice.organization
    cust = invoice.customer
    return InvoicePayload(
        document_no=invoice.document_no,
        invoice_type=invoice.invoice_type.value,
        business_date=invoice.business_date.isoformat(),
        currency=invoice.currency,
        exchange_rate=invoice.exchange_rate,
        seller_tin=org.tin or "",
        seller_name=org.name,
        seller_msic_code=org.msic_code,
        seller_sst_no=org.sst_registration_no,
        buyer_tin=cust.tin or "000000000000",  # B2C fallback per LHDN spec
        buyer_name=cust.name,
        buyer_msic_code=cust.msic_code,
        subtotal_excl_tax=invoice.subtotal_excl_tax,
        tax_amount=invoice.tax_amount,
        total_incl_tax=invoice.total_incl_tax,
        line_count=len(invoice.lines or []),
    )


async def _lazy_finalize_if_due(
    session: AsyncSession,
    invoice: Invoice,
    *,
    actor_user_id: Optional[int] = None,
) -> Invoice:
    """Advance VALIDATED → FINAL on read once the window has elapsed.

    Idempotent: only fires when status is VALIDATED and validated_at is past
    the configured window. Publishes DocumentStatusChanged for audit.
    """
    if (
        invoice.status != InvoiceStatus.VALIDATED
        or invoice.validated_at is None
    ):
        return invoice

    window = get_finalize_window()
    if (_now() - invoice.validated_at) <= window:
        return invoice

    old_status = invoice.status.value
    invoice.status = InvoiceStatus.FINAL
    invoice.finalized_at = _now()
    if actor_user_id is not None:
        invoice.updated_by = actor_user_id
    session.add(invoice)

    await event_bus.publish(
        DocumentStatusChanged(
            document_type="INVOICE",
            document_id=invoice.id,
            document_no=invoice.document_no,
            old_status=old_status,
            new_status=InvoiceStatus.FINAL.value,
            organization_id=invoice.organization_id,
            actor_user_id=actor_user_id,
        ),
        session,
    )
    logger.info(
        "invoice_lazy_finalized",
        invoice_id=invoice.id,
        document_no=invoice.document_no,
    )
    await session.flush()
    return invoice


# ── Public API ───────────────────────────────────────────────────────────────


async def generate_draft_from_so(
    session: AsyncSession,
    *,
    so_id: int,
    org_id: int,
    user: User,
    payload: GenerateFromSOIn,
) -> InvoiceDetail:
    """Create a DRAFT Invoice from a shipped SalesOrder.

    Window 11 constraint: one SO produces at most one Invoice. A second call
    returns the existing Invoice instead of erroring (idempotent).
    """
    so_repo = SalesOrderRepository(session)
    so: Optional[SalesOrder] = await so_repo.get_detail(org_id, so_id)
    if so is None:
        raise NotFoundError(
            message=f"Sales order {so_id} not found.",
            error_code="SO_NOT_FOUND",
        )

    if so.status not in (SOStatus.PARTIAL_SHIPPED, SOStatus.FULLY_SHIPPED):
        raise BusinessRuleError(
            message=(
                f"Cannot generate invoice for SO {so.document_no}: "
                f"SO status is {so.status.value}, "
                "expected PARTIAL_SHIPPED or FULLY_SHIPPED."
            ),
            error_code="SO_NOT_INVOICEABLE",
        )

    repo = InvoiceRepository(session)
    existing = await repo.get_by_so_id(org_id, so.id)
    if existing is not None:
        full = await repo.get_detail(org_id, existing.id)
        # Idempotent: return the existing invoice.
        full = await _lazy_finalize_if_due(session, full, actor_user_id=user.id)
        return _to_detail(full)

    shipped_lines = [ln for ln in so.lines or [] if ln.qty_shipped > 0]
    if not shipped_lines:
        raise BusinessRuleError(
            message=(
                f"SO {so.document_no} has no shipped quantities to invoice."
            ),
            error_code="SO_NOTHING_SHIPPED",
        )

    document_no = await next_document_no(session, "INV", org_id)
    today = payload.business_date or date.today()
    due_date = payload.due_date or (
        today + timedelta(days=so.payment_terms_days)
        if so.payment_terms_days
        else today
    )

    invoice = Invoice(
        organization_id=org_id,
        document_no=document_no,
        invoice_type=InvoiceType.INVOICE,
        status=InvoiceStatus.DRAFT,
        sales_order_id=so.id,
        customer_id=so.customer_id,
        warehouse_id=so.warehouse_id,
        business_date=today,
        due_date=due_date,
        currency=so.currency,
        exchange_rate=so.exchange_rate,
        remarks=payload.remarks,
        created_by=user.id,
    )
    session.add(invoice)
    await session.flush()

    subtotal = Decimal("0")
    tax_total = Decimal("0")
    discount_total = Decimal("0")

    for idx, sol in enumerate(shipped_lines, start=1):
        qty = sol.qty_shipped  # Window 11: invoice everything that's been shipped.
        line_excl = _quantize(qty * sol.unit_price_excl_tax - sol.discount_amount)
        line_tax = _quantize(line_excl * sol.tax_rate_percent / Decimal("100"))
        line_incl = _quantize(line_excl + line_tax)

        inv_line = InvoiceLine(
            invoice_id=invoice.id,
            sales_order_line_id=sol.id,
            line_no=idx,
            sku_id=sol.sku_id,
            description=sol.description or (sol.sku.name if sol.sku else ""),
            uom_id=sol.uom_id,
            qty=qty,
            unit_price_excl_tax=sol.unit_price_excl_tax,
            tax_rate_id=sol.tax_rate_id,
            tax_rate_percent=sol.tax_rate_percent,
            tax_amount=line_tax,
            discount_amount=sol.discount_amount,
            line_total_excl_tax=line_excl,
            line_total_incl_tax=line_incl,
            msic_code=(sol.sku.msic_code if sol.sku and getattr(sol.sku, "msic_code", None) else None),
        )
        session.add(inv_line)

        subtotal += line_excl
        tax_total += line_tax
        discount_total += sol.discount_amount

        # Track invoiced qty on SO line for future partial-invoicing support.
        sol.qty_invoiced = sol.qty_invoiced + qty

    invoice.subtotal_excl_tax = _quantize(subtotal)
    invoice.tax_amount = _quantize(tax_total)
    invoice.discount_amount = _quantize(discount_total)
    invoice.total_incl_tax = _quantize(subtotal + tax_total)
    invoice.base_currency_amount = _quantize(invoice.total_incl_tax * invoice.exchange_rate)
    session.add(invoice)
    await session.flush()

    full = await repo.get_detail(org_id, invoice.id)
    if full is None:  # pragma: no cover — defensive
        raise NotFoundError(message=f"Invoice {invoice.id} disappeared after creation.")

    logger.info(
        "invoice_draft_generated",
        invoice_id=full.id,
        document_no=full.document_no,
        so_id=so.id,
        line_count=len(shipped_lines),
        total=str(full.total_incl_tax),
    )
    return _to_detail(full)


async def submit_to_myinvois(
    session: AsyncSession,
    *,
    invoice_id: int,
    org_id: int,
    user: User,
) -> InvoiceDetail:
    """DRAFT → VALIDATED via the configured adapter (mock by default)."""
    repo = InvoiceRepository(session)
    invoice = await repo.get_detail(org_id, invoice_id)
    if invoice is None:
        raise NotFoundError(
            message=f"Invoice {invoice_id} not found.",
            error_code="INVOICE_NOT_FOUND",
        )
    _assert_status(invoice, {InvoiceStatus.DRAFT}, "submit")

    adapter = get_myinvois_adapter()
    result = await adapter.submit(_build_payload(invoice))

    old_status = invoice.status.value
    invoice.submitted_at = result.submitted_at
    invoice.validated_at = result.validated_at
    invoice.uin = result.uin
    invoice.qr_code_url = result.qr_code_url
    invoice.status = InvoiceStatus.VALIDATED
    invoice.updated_by = user.id
    session.add(invoice)

    await event_bus.publish(
        DocumentStatusChanged(
            document_type="INVOICE",
            document_id=invoice.id,
            document_no=invoice.document_no,
            old_status=old_status,
            new_status=InvoiceStatus.VALIDATED.value,
            organization_id=org_id,
            actor_user_id=user.id,
        ),
        session,
    )
    await event_bus.publish(
        EInvoiceValidated(
            organization_id=org_id,
            invoice_id=invoice.id,
            invoice_no=invoice.document_no,
            uin=result.uin,
            validated_at=result.validated_at.isoformat(),
        ),
        session,
    )

    await session.flush()
    full = await repo.get_detail(org_id, invoice.id)
    logger.info(
        "invoice_submitted",
        invoice_id=full.id,
        document_no=full.document_no,
        uin=full.uin,
    )
    return _to_detail(full)


async def reject_by_buyer(
    session: AsyncSession,
    *,
    invoice_id: int,
    org_id: int,
    user: User,
    payload: RejectByBuyerIn,
) -> InvoiceDetail:
    """VALIDATED → REJECTED, must be within the 72h opposition window."""
    repo = InvoiceRepository(session)
    invoice = await repo.get_detail(org_id, invoice_id)
    if invoice is None:
        raise NotFoundError(
            message=f"Invoice {invoice_id} not found.",
            error_code="INVOICE_NOT_FOUND",
        )
    _assert_status(invoice, {InvoiceStatus.VALIDATED}, "reject")

    if invoice.validated_at is None:
        raise BusinessRuleError(
            message="Invoice has no validated_at timestamp; cannot evaluate rejection window.",
            error_code="INVOICE_MISSING_VALIDATED_AT",
        )
    elapsed = _now() - invoice.validated_at
    window = get_finalize_window()
    if elapsed > window:
        raise BusinessRuleError(
            message=(
                "Rejection window has expired: "
                f"{int(elapsed.total_seconds())}s elapsed, limit {int(window.total_seconds())}s."
            ),
            error_code="INVOICE_REJECTION_WINDOW_EXPIRED",
        )

    # Optional adapter callback — best-effort, mock always succeeds.
    adapter = get_myinvois_adapter()
    if invoice.uin:
        await adapter.reject(invoice.uin, reason=payload.reason)

    old_status = invoice.status.value
    invoice.rejected_at = _now()
    invoice.rejected_by = RejectedBy.BUYER
    invoice.rejection_reason = payload.reason
    invoice.rejection_attachment_id = payload.rejection_attachment_id
    invoice.status = InvoiceStatus.REJECTED
    invoice.updated_by = user.id
    session.add(invoice)

    await event_bus.publish(
        DocumentStatusChanged(
            document_type="INVOICE",
            document_id=invoice.id,
            document_no=invoice.document_no,
            old_status=old_status,
            new_status=InvoiceStatus.REJECTED.value,
            organization_id=org_id,
            actor_user_id=user.id,
        ),
        session,
    )
    await session.flush()
    full = await repo.get_detail(org_id, invoice.id)
    logger.info(
        "invoice_rejected_by_buyer",
        invoice_id=full.id,
        document_no=full.document_no,
        reason=payload.reason,
    )
    return _to_detail(full)


async def get_invoice(
    session: AsyncSession,
    invoice_id: int,
    *,
    org_id: int,
    user: Optional[User] = None,
) -> InvoiceDetail:
    repo = InvoiceRepository(session)
    invoice = await repo.get_detail(org_id, invoice_id)
    if invoice is None:
        raise NotFoundError(
            message=f"Invoice {invoice_id} not found.",
            error_code="INVOICE_NOT_FOUND",
        )
    invoice = await _lazy_finalize_if_due(
        session, invoice, actor_user_id=user.id if user else None
    )
    return _to_detail(invoice)


async def list_invoices(
    session: AsyncSession,
    pagination: PaginationParams,
    *,
    org_id: int,
    status: Optional[InvoiceStatus] = None,
    customer_id: Optional[int] = None,
    sales_order_id: Optional[int] = None,
    search: Optional[str] = None,
) -> PaginatedResponse[InvoiceListItem]:
    repo = InvoiceRepository(session)
    items, total = await repo.list_with_filters(
        org_id,
        status=status,
        customer_id=customer_id,
        sales_order_id=sales_order_id,
        search=search,
        limit=pagination.page_size,
        offset=pagination.offset,
    )
    response_items = [_to_list_item(it) for it in items]
    return PaginatedResponse[InvoiceListItem].build(
        items=response_items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


async def run_finalize_scan(
    session: AsyncSession,
    *,
    org_id: int,
    user: User,
) -> FinalizeScanResult:
    """Bulk advance VALIDATED → FINAL for all expired invoices.

    Used by the admin button. Publishes a single aggregate
    DocumentStatusChanged event with document_id=0 for audit visibility.
    """
    repo = InvoiceRepository(session)
    window = get_finalize_window()
    now = _now()
    cutoff = now - window

    count = await repo.bulk_finalize(org_id, cutoff=cutoff, now=now)
    if count > 0:
        await event_bus.publish(
            DocumentStatusChanged(
                document_type="INVOICE",
                document_id=0,
                document_no=f"<batch-finalize x{count}>",
                old_status=InvoiceStatus.VALIDATED.value,
                new_status=InvoiceStatus.FINAL.value,
                organization_id=org_id,
                actor_user_id=user.id,
            ),
            session,
        )
        logger.info(
            "invoice_bulk_finalized",
            org_id=org_id,
            count=count,
        )
    return FinalizeScanResult(
        finalized_count=count,
        finalize_window_seconds=int(window.total_seconds()),
    )
