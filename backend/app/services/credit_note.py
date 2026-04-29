"""Credit Note service — Window 12.

Three core operations:

* ``create_credit_note`` — DRAFT CN against a VALIDATED/FINAL invoice. Validates
  per-line and cumulative quantity caps, computes line/header totals from the
  original invoice's unit prices and tax rates, then inbounds the returned
  goods to stock via ``inventory.apply_sales_return`` using the SOLine's
  ``snapshot_avg_cost`` so the warehouse weighted-average is not polluted.
* ``submit_credit_note_to_myinvois`` — DRAFT → VALIDATED via the configured
  adapter (mock by default). Publishes ``DocumentStatusChanged(document_type='CN')``
  and ``EInvoiceValidated`` so the buyer notification handler fires.
* ``cancel_credit_note`` — DRAFT only. Reverses the inbound by calling
  ``inventory.apply_sales_out`` for each line, transitions to CANCELLED.
  ``SUBMITTED``/``VALIDATED`` cannot be cancelled in Window 12 (LHDN-side state
  is final once accepted).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BusinessRuleError,
    InvalidStatusTransitionError,
    NotFoundError,
)
from app.enums import (
    CreditNoteStatus,
    InvoiceStatus,
)
from app.events import event_bus
from app.events.types import DocumentStatusChanged, EInvoiceValidated
from app.integrations.myinvois import InvoicePayload
from app.integrations.myinvois_factory import get_myinvois_adapter
from app.models.invoice import CreditNote, CreditNoteLine, Invoice
from app.models.organization import User
from app.repositories.credit_note import CreditNoteRepository
from app.repositories.invoice import InvoiceRepository
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.credit_note import (
    CreditNoteCreateIn,
    CreditNoteDetail,
    CreditNoteLineResponse,
    CreditNoteListItem,
)
from app.services import inventory as inventory_svc
from app.services.sequence import next_document_no

logger = structlog.get_logger()

_FOUR = Decimal("0.0001")


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _quantize(v: Decimal) -> Decimal:
    return v.quantize(_FOUR, rounding=ROUND_HALF_UP)


# ── Mappers ──────────────────────────────────────────────────────────────────


def _to_list_item(cn: CreditNote) -> CreditNoteListItem:
    item = CreditNoteListItem.model_validate(cn)
    if cn.invoice is not None:
        item.invoice_no = cn.invoice.document_no
    if cn.customer is not None:
        item.customer_name = cn.customer.name
    return item


def _to_detail(cn: CreditNote) -> CreditNoteDetail:
    detail = CreditNoteDetail.model_validate(cn)
    if cn.invoice is not None:
        detail.invoice_no = cn.invoice.document_no
    if cn.customer is not None:
        detail.customer_name = cn.customer.name
    line_resps: list[CreditNoteLineResponse] = []
    for ln in cn.lines or []:
        resp = CreditNoteLineResponse.model_validate(ln)
        if ln.sku is not None:
            resp.sku_code = ln.sku.code
            resp.sku_name = ln.sku.name
        if ln.uom is not None:
            resp.uom_code = ln.uom.code
        line_resps.append(resp)
    detail.lines = line_resps
    return detail


def _assert_status(
    cn: CreditNote, allowed: set[CreditNoteStatus], action: str
) -> None:
    if cn.status not in allowed:
        raise InvalidStatusTransitionError(
            message=(
                f"Cannot {action} credit note {cn.document_no}: "
                f"current status is {cn.status.value}, "
                f"expected one of {sorted(s.value for s in allowed)}."
            ),
            error_code="CREDIT_NOTE_INVALID_STATUS",
        )


# ── Payload for MyInvois (CN flavour) ─────────────────────────────────────────


def _build_cn_payload(cn: CreditNote) -> InvoicePayload:
    org = cn.organization
    cust = cn.customer
    return InvoicePayload(
        document_no=cn.document_no,
        invoice_type="CREDIT_NOTE",
        business_date=cn.business_date.isoformat(),
        currency=cn.currency,
        exchange_rate=cn.exchange_rate,
        seller_tin=(org.tin or "") if org else "",
        seller_name=org.name if org else "",
        seller_msic_code=(org.msic_code or None) if org else None,
        seller_sst_no=(org.sst_registration_no or None) if org else None,
        buyer_tin=(cust.tin or "000000000000") if cust else "000000000000",
        buyer_name=cust.name if cust else "",
        buyer_msic_code=(cust.msic_code or None) if cust else None,
        subtotal_excl_tax=cn.subtotal_excl_tax,
        tax_amount=cn.tax_amount,
        total_incl_tax=cn.total_incl_tax,
        line_count=len(cn.lines or []),
    )


# ── Public API ───────────────────────────────────────────────────────────────


async def create_credit_note(
    session: AsyncSession,
    *,
    org_id: int,
    user: User,
    payload: CreditNoteCreateIn,
) -> CreditNoteDetail:
    """Create a DRAFT Credit Note and inbound the returned goods to stock.

    Quantity validation:
    * per-line: requested qty <= original invoice line qty.
    * cumulative: requested qty + already-credited (non-cancelled CNs) <= original qty.
    """
    inv_repo = InvoiceRepository(session)
    invoice: Optional[Invoice] = await inv_repo.get_detail(org_id, payload.invoice_id)
    if invoice is None:
        raise NotFoundError(
            message=f"Invoice {payload.invoice_id} not found.",
            error_code="INVOICE_NOT_FOUND",
        )

    if invoice.status not in (InvoiceStatus.VALIDATED, InvoiceStatus.FINAL):
        raise BusinessRuleError(
            message=(
                f"Cannot credit invoice {invoice.document_no}: status is "
                f"{invoice.status.value}; only VALIDATED or FINAL invoices can be credited."
            ),
            error_code="INVOICE_NOT_CREDITABLE",
        )

    if invoice.warehouse_id is None:
        raise BusinessRuleError(
            message=(
                f"Invoice {invoice.document_no} has no warehouse on record; "
                "cannot determine where to return the goods."
            ),
            error_code="INVOICE_WAREHOUSE_MISSING",
        )

    # ── Validate every requested line ────────────────────────────────────────
    inv_lines_by_id = {ln.id: ln for ln in (invoice.lines or [])}
    cn_repo = CreditNoteRepository(session)
    already_credited = await cn_repo.sum_credited_qty_per_invoice_line(invoice.id)

    for line_in in payload.lines:
        inv_line = inv_lines_by_id.get(line_in.invoice_line_id)
        if inv_line is None:
            raise BusinessRuleError(
                message=(
                    f"Invoice line {line_in.invoice_line_id} does not belong to "
                    f"invoice {invoice.document_no}."
                ),
                error_code="CREDIT_NOTE_LINE_MISMATCH",
            )
        prior = already_credited.get(inv_line.id, Decimal("0"))
        max_creditable = inv_line.qty - prior
        if line_in.qty > max_creditable:
            raise BusinessRuleError(
                message=(
                    f"Line {inv_line.line_no}: requested {line_in.qty} but only "
                    f"{max_creditable} remain creditable "
                    f"(invoiced {inv_line.qty}, already credited {prior})."
                ),
                error_code="CREDIT_NOTE_QTY_EXCEEDS_INVOICE",
            )

    # ── Build the CN ─────────────────────────────────────────────────────────
    document_no = await next_document_no(session, "CN", org_id)
    business_date = payload.business_date or date.today()

    cn = CreditNote(
        organization_id=org_id,
        document_no=document_no,
        status=CreditNoteStatus.DRAFT,
        invoice_id=invoice.id,
        customer_id=invoice.customer_id,
        business_date=business_date,
        reason=payload.reason,
        reason_description=payload.reason_description,
        currency=invoice.currency,
        exchange_rate=invoice.exchange_rate,
        remarks=payload.remarks,
        created_by=user.id,
    )
    session.add(cn)
    await session.flush()

    # ── Lines + stock inbound ────────────────────────────────────────────────
    subtotal = Decimal("0")
    tax_total = Decimal("0")

    for idx, line_in in enumerate(payload.lines, start=1):
        inv_line = inv_lines_by_id[line_in.invoice_line_id]
        qty = line_in.qty

        # Use the original invoice line's unit price + tax rate so the CN math
        # mirrors what was billed.
        line_excl = _quantize(qty * inv_line.unit_price_excl_tax)
        line_tax = _quantize(line_excl * inv_line.tax_rate_percent / Decimal("100"))
        line_incl = _quantize(line_excl + line_tax)

        # snapshot_avg_cost path: InvoiceLine → SalesOrderLine → snapshot
        sol = inv_line.sales_order_line
        snapshot_cost = sol.snapshot_avg_cost if sol is not None else None
        # Fallback when there's no SOL link (e.g. legacy data) — use 0 so the
        # weighted-average computation degenerates to "current avg unchanged
        # for the on_hand portion plus 0-cost incoming." Surfacing this via
        # logger so it's visible during demo.
        unit_cost_for_inbound = (
            snapshot_cost if snapshot_cost is not None else Decimal("0")
        )
        if snapshot_cost is None:
            logger.warning(
                "credit_note_no_snapshot_cost",
                invoice_line_id=inv_line.id,
                document_no=invoice.document_no,
            )

        cn_line = CreditNoteLine(
            credit_note_id=cn.id,
            invoice_line_id=inv_line.id,
            line_no=idx,
            sku_id=inv_line.sku_id,
            description=line_in.description or inv_line.description,
            uom_id=inv_line.uom_id,
            qty=qty,
            unit_price_excl_tax=inv_line.unit_price_excl_tax,
            tax_rate_percent=inv_line.tax_rate_percent,
            tax_amount=line_tax,
            line_total_excl_tax=line_excl,
            line_total_incl_tax=line_incl,
            snapshot_avg_cost=snapshot_cost,
        )
        session.add(cn_line)

        subtotal += line_excl
        tax_total += line_tax

        # Inbound the returned goods.
        await inventory_svc.apply_sales_return(
            session,
            org_id=org_id,
            sku_id=inv_line.sku_id,
            warehouse_id=invoice.warehouse_id,
            qty=qty,
            unit_cost=unit_cost_for_inbound,
            source_document_id=cn.id,
            source_line_id=cn_line.id if cn_line.id else None,
            actor_user_id=user.id,
        )

    cn.subtotal_excl_tax = _quantize(subtotal)
    cn.tax_amount = _quantize(tax_total)
    cn.total_incl_tax = _quantize(subtotal + tax_total)
    cn.base_currency_amount = _quantize(cn.total_incl_tax * cn.exchange_rate)
    session.add(cn)
    await session.flush()

    full = await cn_repo.get_detail(org_id, cn.id)
    if full is None:  # pragma: no cover — defensive
        raise NotFoundError(message=f"CreditNote {cn.id} disappeared after creation.")

    logger.info(
        "credit_note_drafted",
        cn_id=cn.id,
        document_no=cn.document_no,
        invoice_id=invoice.id,
        line_count=len(payload.lines),
        total=str(cn.total_incl_tax),
    )
    return _to_detail(full)


async def submit_credit_note_to_myinvois(
    session: AsyncSession,
    *,
    cn_id: int,
    org_id: int,
    user: User,
) -> CreditNoteDetail:
    """DRAFT → VALIDATED via the configured MyInvois adapter."""
    repo = CreditNoteRepository(session)
    cn = await repo.get_detail(org_id, cn_id)
    if cn is None:
        raise NotFoundError(
            message=f"Credit Note {cn_id} not found.",
            error_code="CREDIT_NOTE_NOT_FOUND",
        )
    _assert_status(cn, {CreditNoteStatus.DRAFT}, "submit")

    adapter = get_myinvois_adapter()
    result = await adapter.submit(_build_cn_payload(cn))

    old_status = cn.status.value
    cn.submitted_at = result.submitted_at
    cn.validated_at = result.validated_at
    cn.uin = result.uin
    cn.qr_code_url = result.qr_code_url
    cn.status = CreditNoteStatus.VALIDATED
    cn.updated_by = user.id
    session.add(cn)

    await event_bus.publish(
        DocumentStatusChanged(
            document_type="CN",
            document_id=cn.id,
            document_no=cn.document_no,
            old_status=old_status,
            new_status=CreditNoteStatus.VALIDATED.value,
            organization_id=org_id,
            actor_user_id=user.id,
        ),
        session,
    )
    # Reuse the buyer-notification path so customers see a CN-validated entry
    # in their notification centre alongside invoice validation events.
    await event_bus.publish(
        EInvoiceValidated(
            organization_id=org_id,
            invoice_id=cn.id,  # reused field — handler treats it opaquely
            invoice_no=cn.document_no,
            uin=result.uin,
            validated_at=result.validated_at.isoformat(),
        ),
        session,
    )

    await session.flush()
    full = await repo.get_detail(org_id, cn.id)
    logger.info(
        "credit_note_submitted",
        cn_id=full.id,
        document_no=full.document_no,
        uin=full.uin,
    )
    return _to_detail(full)


async def cancel_credit_note(
    session: AsyncSession,
    *,
    cn_id: int,
    org_id: int,
    user: User,
) -> CreditNoteDetail:
    """DRAFT → CANCELLED, with stock rollback (re-issue sales-out for each line)."""
    repo = CreditNoteRepository(session)
    cn = await repo.get_detail(org_id, cn_id)
    if cn is None:
        raise NotFoundError(
            message=f"Credit Note {cn_id} not found.",
            error_code="CREDIT_NOTE_NOT_FOUND",
        )
    _assert_status(cn, {CreditNoteStatus.DRAFT}, "cancel")

    if cn.invoice is None or cn.invoice.warehouse_id is None:
        raise BusinessRuleError(
            message="Cannot roll back stock: invoice warehouse is unknown.",
            error_code="INVOICE_WAREHOUSE_MISSING",
        )

    # Roll the inbound back. We use apply_sales_out to symmetrically deduct the
    # qty we previously added; this writes a SALES movement against CN id, which
    # is loud in the audit trail (intentional — cancellations should be visible).
    for ln in cn.lines or []:
        await inventory_svc.apply_sales_out(
            session,
            org_id=org_id,
            sku_id=ln.sku_id,
            warehouse_id=cn.invoice.warehouse_id,
            qty=ln.qty,
            source_document_id=cn.id,
            source_line_id=ln.id,
            actor_user_id=user.id,
            notes=f"CN cancellation rollback ({cn.document_no})",
        )

    old_status = cn.status.value
    cn.status = CreditNoteStatus.CANCELLED
    cn.updated_by = user.id
    session.add(cn)

    await event_bus.publish(
        DocumentStatusChanged(
            document_type="CN",
            document_id=cn.id,
            document_no=cn.document_no,
            old_status=old_status,
            new_status=CreditNoteStatus.CANCELLED.value,
            organization_id=org_id,
            actor_user_id=user.id,
        ),
        session,
    )
    await session.flush()
    full = await repo.get_detail(org_id, cn.id)
    logger.info(
        "credit_note_cancelled",
        cn_id=full.id,
        document_no=full.document_no,
    )
    return _to_detail(full)


async def get_credit_note(
    session: AsyncSession,
    cn_id: int,
    *,
    org_id: int,
) -> CreditNoteDetail:
    repo = CreditNoteRepository(session)
    cn = await repo.get_detail(org_id, cn_id)
    if cn is None:
        raise NotFoundError(
            message=f"Credit Note {cn_id} not found.",
            error_code="CREDIT_NOTE_NOT_FOUND",
        )
    return _to_detail(cn)


async def list_credit_notes(
    session: AsyncSession,
    pagination: PaginationParams,
    *,
    org_id: int,
    status: Optional[CreditNoteStatus] = None,
    invoice_id: Optional[int] = None,
    customer_id: Optional[int] = None,
    search: Optional[str] = None,
) -> PaginatedResponse[CreditNoteListItem]:
    repo = CreditNoteRepository(session)
    items, total = await repo.list_with_filters(
        org_id,
        status=status,
        invoice_id=invoice_id,
        customer_id=customer_id,
        search=search,
        limit=pagination.page_size,
        offset=pagination.offset,
    )
    response_items = [_to_list_item(it) for it in items]
    return PaginatedResponse[CreditNoteListItem].build(
        items=response_items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )
