"""
Purchase Order service — CRUD + state machine.

State machine (W7 scope):
    DRAFT ──confirm──▶ CONFIRMED   (Stock.incoming += qty)
    DRAFT ──cancel──▶  CANCELLED
    CONFIRMED ──cancel──▶ CANCELLED (Manager/Admin only, Stock.incoming -= qty)

GoodsReceipt and PARTIAL/FULLY_RECEIVED transitions are in W8.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

import structlog
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthorizationError,
    BusinessRuleError,
    InvalidStatusTransitionError,
    NotFoundError,
    ValidationError,
)
from app.enums import POSource, POStatus, RoleCode
from app.events import event_bus
from app.events.types import DocumentStatusChanged
from app.models.organization import User
from app.models.purchase import PurchaseOrder, PurchaseOrderLine
from app.models.stock import Stock
from app.repositories.purchase_order import PurchaseOrderRepository
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.purchase_order import (
    POLineCreate,
    POLineResponse,
    PurchaseOrderCancel,
    PurchaseOrderCreate,
    PurchaseOrderDetail,
    PurchaseOrderResponse,
    PurchaseOrderUpdate,
)
from app.services.sequence import next_document_no

logger = structlog.get_logger()

_TWO = Decimal("0.01")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _calc_line(line_in: POLineCreate, line_no: int) -> dict:
    qty = line_in.qty_ordered.quantize(_TWO, ROUND_HALF_UP)
    price = line_in.unit_price_excl_tax.quantize(_TWO, ROUND_HALF_UP)
    disc_pct = line_in.discount_percent.quantize(_TWO, ROUND_HALF_UP)
    tax_pct = line_in.tax_rate_percent.quantize(_TWO, ROUND_HALF_UP)

    gross = (qty * price).quantize(_TWO, ROUND_HALF_UP)
    disc_amt = (gross * disc_pct / Decimal("100")).quantize(_TWO, ROUND_HALF_UP)
    excl_tax = (gross - disc_amt).quantize(_TWO, ROUND_HALF_UP)
    tax_amt = (excl_tax * tax_pct / Decimal("100")).quantize(_TWO, ROUND_HALF_UP)
    incl_tax = (excl_tax + tax_amt).quantize(_TWO, ROUND_HALF_UP)

    return {
        "line_no": line_no,
        "sku_id": line_in.sku_id,
        "uom_id": line_in.uom_id,
        "description": line_in.description,
        "qty_ordered": qty,
        "qty_received": Decimal("0"),
        "unit_price_excl_tax": price,
        "tax_rate_id": line_in.tax_rate_id,
        "tax_rate_percent": tax_pct,
        "discount_percent": disc_pct,
        "discount_amount": disc_amt,
        "tax_amount": tax_amt,
        "line_total_excl_tax": excl_tax,
        "line_total_incl_tax": incl_tax,
        "batch_no": line_in.batch_no,
        "expiry_date": line_in.expiry_date,
    }


def _calc_totals(line_dicts: list[dict]) -> dict:
    subtotal = sum((d["line_total_excl_tax"] for d in line_dicts), Decimal("0"))
    tax = sum((d["tax_amount"] for d in line_dicts), Decimal("0"))
    disc = sum((d["discount_amount"] for d in line_dicts), Decimal("0"))
    total = (subtotal + tax).quantize(_TWO, ROUND_HALF_UP)
    return {
        "subtotal_excl_tax": subtotal.quantize(_TWO, ROUND_HALF_UP),
        "tax_amount": tax.quantize(_TWO, ROUND_HALF_UP),
        "discount_amount": disc.quantize(_TWO, ROUND_HALF_UP),
        "total_incl_tax": total,
    }


def _to_response(po: PurchaseOrder) -> PurchaseOrderDetail:
    lines = [POLineResponse.model_validate(ln) for ln in (po.lines or [])]
    detail = PurchaseOrderDetail.model_validate(po)
    detail.lines = lines
    return detail


# ── Stock helpers ─────────────────────────────────────────────────────────────

async def _adjust_incoming(
    session: AsyncSession,
    org_id: int,
    warehouse_id: int,
    lines: list[PurchaseOrderLine],
    delta: int,  # +1 or -1
) -> None:
    """Atomically adjust Stock.incoming for each PO line."""
    now = datetime.now(UTC).replace(tzinfo=None)
    for line in lines:
        # Get-or-create stock row
        stmt = select(Stock).where(
            Stock.sku_id == line.sku_id,
            Stock.warehouse_id == warehouse_id,
        )
        result = await session.execute(stmt)
        stock = result.scalar_one_or_none()

        if stock is None:
            stock = Stock(
                organization_id=org_id,
                sku_id=line.sku_id,
                warehouse_id=warehouse_id,
                on_hand=Decimal("0"),
                reserved=Decimal("0"),
                quality_hold=Decimal("0"),
                incoming=max(Decimal("0"), line.qty_ordered * delta),
                in_transit=Decimal("0"),
                avg_cost=line.unit_price_excl_tax,
                last_movement_at=now,
            )
            session.add(stock)
        else:
            # Atomic update to avoid race conditions
            await session.execute(
                update(Stock)
                .where(Stock.id == stock.id)
                .values(
                    incoming=Stock.incoming + line.qty_ordered * delta,
                    last_movement_at=now,
                )
            )


# ── Public API ────────────────────────────────────────────────────────────────

async def list_pos(
    session: AsyncSession,
    pagination: PaginationParams,
    *,
    org_id: int,
    status: POStatus | None = None,
    supplier_id: int | None = None,
    warehouse_id: int | None = None,
    search: str | None = None,
) -> PaginatedResponse[PurchaseOrderResponse]:
    repo = PurchaseOrderRepository(session)
    items, total = await repo.list_with_filters(
        org_id,
        status=status,
        supplier_id=supplier_id,
        warehouse_id=warehouse_id,
        search=search,
        limit=pagination.page_size,
        offset=pagination.offset,
    )
    return PaginatedResponse[PurchaseOrderResponse].build(
        items=[PurchaseOrderResponse.model_validate(po) for po in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


async def get_po(
    session: AsyncSession,
    po_id: int,
    *,
    org_id: int,
) -> PurchaseOrderDetail:
    repo = PurchaseOrderRepository(session)
    po = await repo.get_detail(org_id, po_id)
    if po is None:
        raise NotFoundError(message=f"Purchase order {po_id} not found.")
    return _to_response(po)


async def create_po(
    session: AsyncSession,
    data: PurchaseOrderCreate,
    *,
    org_id: int,
    user: User,
) -> PurchaseOrderDetail:
    document_no = await next_document_no(session, "PO", org_id)
    line_dicts = [_calc_line(ln, idx + 1) for idx, ln in enumerate(data.lines)]
    totals = _calc_totals(line_dicts)

    exchange_rate = data.exchange_rate.quantize(Decimal("0.00000001"), ROUND_HALF_UP)
    base_amount = (totals["total_incl_tax"] * exchange_rate).quantize(_TWO, ROUND_HALF_UP)

    po = PurchaseOrder(
        organization_id=org_id,
        document_no=document_no,
        status=POStatus.DRAFT,
        source=POSource.MANUAL,
        supplier_id=data.supplier_id,
        warehouse_id=data.warehouse_id,
        business_date=data.business_date,
        expected_date=data.expected_date,
        currency=data.currency,
        exchange_rate=exchange_rate,
        payment_terms_days=data.payment_terms_days,
        remarks=data.remarks,
        shipping_amount=Decimal("0"),
        base_currency_amount=base_amount,
        created_by=user.id,
        updated_by=user.id,
        **totals,
    )
    session.add(po)
    await session.flush()

    for ld in line_dicts:
        session.add(PurchaseOrderLine(purchase_order_id=po.id, **ld))

    await session.flush()
    await session.refresh(po)
    # Reload lines
    repo = PurchaseOrderRepository(session)
    po = await repo.get_detail(org_id, po.id)  # type: ignore[assignment]

    logger.info("po_created", po_id=po.id, document_no=po.document_no, org_id=org_id)
    return _to_response(po)  # type: ignore[arg-type]


async def update_po(
    session: AsyncSession,
    po_id: int,
    data: PurchaseOrderUpdate,
    *,
    org_id: int,
    user: User,
) -> PurchaseOrderDetail:
    repo = PurchaseOrderRepository(session)
    po = await repo.get_detail(org_id, po_id)
    if po is None:
        raise NotFoundError(message=f"Purchase order {po_id} not found.")
    if po.status != POStatus.DRAFT:
        raise BusinessRuleError(
            message="Only DRAFT purchase orders can be edited.",
            error_code="PO_NOT_EDITABLE",
        )

    update_fields: dict = {"updated_by": user.id}
    if data.supplier_id is not None:
        update_fields["supplier_id"] = data.supplier_id
    if data.warehouse_id is not None:
        update_fields["warehouse_id"] = data.warehouse_id
    if data.business_date is not None:
        update_fields["business_date"] = data.business_date
    if data.expected_date is not None:
        update_fields["expected_date"] = data.expected_date
    if data.currency is not None:
        update_fields["currency"] = data.currency
    if data.exchange_rate is not None:
        update_fields["exchange_rate"] = data.exchange_rate.quantize(
            Decimal("0.00000001"), ROUND_HALF_UP
        )
    if data.payment_terms_days is not None:
        update_fields["payment_terms_days"] = data.payment_terms_days
    if data.remarks is not None:
        update_fields["remarks"] = data.remarks

    if data.lines is not None:
        # Replace all lines
        for line in po.lines:
            await session.delete(line)
        await session.flush()

        line_dicts = [_calc_line(ln, idx + 1) for idx, ln in enumerate(data.lines)]
        totals = _calc_totals(line_dicts)
        update_fields.update(totals)

        exchange_rate = update_fields.get("exchange_rate", po.exchange_rate)
        update_fields["base_currency_amount"] = (
            totals["total_incl_tax"] * exchange_rate
        ).quantize(_TWO, ROUND_HALF_UP)

        for ld in line_dicts:
            session.add(PurchaseOrderLine(purchase_order_id=po.id, **ld))

    for k, v in update_fields.items():
        setattr(po, k, v)
    session.add(po)
    await session.flush()

    po = await repo.get_detail(org_id, po_id)  # type: ignore[assignment]
    return _to_response(po)  # type: ignore[arg-type]


async def confirm_po(
    session: AsyncSession,
    po_id: int,
    *,
    org_id: int,
    user: User,
) -> PurchaseOrderDetail:
    repo = PurchaseOrderRepository(session)
    po = await repo.get_detail(org_id, po_id)
    if po is None:
        raise NotFoundError(message=f"Purchase order {po_id} not found.")
    if po.status != POStatus.DRAFT:
        raise InvalidStatusTransitionError(
            message=f"Cannot confirm a purchase order in {po.status.value} status."
        )
    if not po.lines:
        raise BusinessRuleError(
            message="Cannot confirm a purchase order with no lines.",
            error_code="PO_NO_LINES",
        )

    now = datetime.now(UTC).replace(tzinfo=None)
    old_status = po.status.value
    po.status = POStatus.CONFIRMED
    po.confirmed_at = now
    po.updated_by = user.id
    session.add(po)

    await _adjust_incoming(session, org_id, po.warehouse_id, po.lines, delta=1)

    await event_bus.publish(
        DocumentStatusChanged(
            document_type="PO",
            document_id=po.id,
            document_no=po.document_no,
            old_status=old_status,
            new_status=POStatus.CONFIRMED.value,
            organization_id=org_id,
            actor_user_id=user.id,
        ),
        session,
    )

    await session.flush()
    po = await repo.get_detail(org_id, po_id)  # type: ignore[assignment]
    logger.info("po_confirmed", po_id=po_id, document_no=po.document_no)  # type: ignore[union-attr]
    return _to_response(po)  # type: ignore[arg-type]


async def cancel_po(
    session: AsyncSession,
    po_id: int,
    data: PurchaseOrderCancel,
    *,
    org_id: int,
    user: User,
) -> PurchaseOrderDetail:
    repo = PurchaseOrderRepository(session)
    po = await repo.get_detail(org_id, po_id)
    if po is None:
        raise NotFoundError(message=f"Purchase order {po_id} not found.")

    if po.status not in (POStatus.DRAFT, POStatus.CONFIRMED):
        raise InvalidStatusTransitionError(
            message=f"Cannot cancel a purchase order in {po.status.value} status."
        )

    # CONFIRMED cancellation requires Manager or Admin
    if po.status == POStatus.CONFIRMED:
        user_roles = {r.code for r in user.roles} if user.roles else set()
        allowed = {RoleCode.ADMIN.value, RoleCode.MANAGER.value}
        if not user_roles & allowed:
            raise AuthorizationError(
                message="Only Manager or Admin can cancel a confirmed purchase order."
            )

    now = datetime.now(UTC).replace(tzinfo=None)
    old_status = po.status.value
    was_confirmed = po.status == POStatus.CONFIRMED

    po.status = POStatus.CANCELLED
    po.cancelled_at = now
    po.cancel_reason = data.cancel_reason
    po.updated_by = user.id
    session.add(po)

    if was_confirmed:
        await _adjust_incoming(session, org_id, po.warehouse_id, po.lines, delta=-1)

    await event_bus.publish(
        DocumentStatusChanged(
            document_type="PO",
            document_id=po.id,
            document_no=po.document_no,
            old_status=old_status,
            new_status=POStatus.CANCELLED.value,
            organization_id=org_id,
            actor_user_id=user.id,
        ),
        session,
    )

    await session.flush()
    po = await repo.get_detail(org_id, po_id)  # type: ignore[assignment]
    logger.info("po_cancelled", po_id=po_id, reason=data.cancel_reason)
    return _to_response(po)  # type: ignore[arg-type]
