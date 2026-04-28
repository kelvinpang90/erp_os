"""
Sales Order service — CRUD + state machine.

State machine (W10 scope):
    DRAFT ──confirm──▶ CONFIRMED   (Stock.reserved += qty per line; throws
                                    InsufficientStockError if available < qty)
    DRAFT ──cancel──▶  CANCELLED
    CONFIRMED ──cancel──▶ CANCELLED (Manager/Admin only, Stock.reserved -= qty)

Shipping (CONFIRMED → PARTIAL_SHIPPED → FULLY_SHIPPED) is handled in
``services.delivery_order.create_do`` which mutates SO.status from there.

Invoicing / payment transitions (FULLY_SHIPPED → INVOICED → PAID) are out of
scope for Window 10 (handled by Window 11/12).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthorizationError,
    BusinessRuleError,
    InvalidStatusTransitionError,
    NotFoundError,
)
from app.enums import RoleCode, SOStatus
from app.events import event_bus
from app.events.types import DocumentStatusChanged
from app.models.organization import User
from app.models.sales import SalesOrder, SalesOrderLine
from app.repositories.sales_order import SalesOrderRepository
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.sales_order import (
    SalesOrderCancel,
    SalesOrderCreate,
    SalesOrderDetail,
    SalesOrderResponse,
    SalesOrderUpdate,
    SOLineCreate,
    SOLineResponse,
)
from app.services import inventory as inventory_svc
from app.services.sequence import next_document_no

logger = structlog.get_logger()

_TWO = Decimal("0.01")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _calc_line(line_in: SOLineCreate, line_no: int) -> dict:
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
        "qty_shipped": Decimal("0"),
        "qty_invoiced": Decimal("0"),
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
        "serial_no": line_in.serial_no,
    }


def _calc_totals(line_dicts: list[dict], shipping_amount: Decimal) -> dict:
    subtotal = sum((d["line_total_excl_tax"] for d in line_dicts), Decimal("0"))
    tax = sum((d["tax_amount"] for d in line_dicts), Decimal("0"))
    disc = sum((d["discount_amount"] for d in line_dicts), Decimal("0"))
    shipping = shipping_amount.quantize(_TWO, ROUND_HALF_UP)
    total = (subtotal + tax + shipping).quantize(_TWO, ROUND_HALF_UP)
    return {
        "subtotal_excl_tax": subtotal.quantize(_TWO, ROUND_HALF_UP),
        "tax_amount": tax.quantize(_TWO, ROUND_HALF_UP),
        "discount_amount": disc.quantize(_TWO, ROUND_HALF_UP),
        "shipping_amount": shipping,
        "total_incl_tax": total,
    }


def _to_response(so: SalesOrder) -> SalesOrderDetail:
    lines = []
    for ln in so.lines or []:
        resp = SOLineResponse.model_validate(ln)
        resp.sku_code = ln.sku.code if ln.sku else ""
        resp.sku_name = ln.sku.name if ln.sku else ""
        lines.append(resp)
    detail = SalesOrderDetail.model_validate(so)
    detail.lines = lines
    detail.customer_name = so.customer.name if so.customer is not None else ""
    detail.warehouse_name = so.warehouse.name if so.warehouse is not None else ""
    return detail


# ── Public API ────────────────────────────────────────────────────────────────

async def list_sos(
    session: AsyncSession,
    pagination: PaginationParams,
    *,
    org_id: int,
    status: SOStatus | None = None,
    customer_id: int | None = None,
    warehouse_id: int | None = None,
    search: str | None = None,
) -> PaginatedResponse[SalesOrderResponse]:
    repo = SalesOrderRepository(session)
    items, total = await repo.list_with_filters(
        org_id,
        status=status,
        customer_id=customer_id,
        warehouse_id=warehouse_id,
        search=search,
        limit=pagination.page_size,
        offset=pagination.offset,
    )
    return PaginatedResponse[SalesOrderResponse].build(
        items=[SalesOrderResponse.model_validate(so) for so in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


async def get_so(
    session: AsyncSession,
    so_id: int,
    *,
    org_id: int,
) -> SalesOrderDetail:
    repo = SalesOrderRepository(session)
    so = await repo.get_detail(org_id, so_id)
    if so is None:
        raise NotFoundError(message=f"Sales order {so_id} not found.")
    return _to_response(so)


async def create_so(
    session: AsyncSession,
    data: SalesOrderCreate,
    *,
    org_id: int,
    user: User,
) -> SalesOrderDetail:
    document_no = await next_document_no(session, "SO", org_id)
    line_dicts = [_calc_line(ln, idx + 1) for idx, ln in enumerate(data.lines)]
    totals = _calc_totals(line_dicts, data.shipping_amount)

    exchange_rate = data.exchange_rate.quantize(Decimal("0.00000001"), ROUND_HALF_UP)
    base_amount = (totals["total_incl_tax"] * exchange_rate).quantize(_TWO, ROUND_HALF_UP)

    so = SalesOrder(
        organization_id=org_id,
        document_no=document_no,
        status=SOStatus.DRAFT,
        customer_id=data.customer_id,
        warehouse_id=data.warehouse_id,
        business_date=data.business_date,
        expected_ship_date=data.expected_ship_date,
        currency=data.currency,
        exchange_rate=exchange_rate,
        payment_terms_days=data.payment_terms_days,
        shipping_address=data.shipping_address,
        remarks=data.remarks,
        base_currency_amount=base_amount,
        created_by=user.id,
        updated_by=user.id,
        **totals,
    )
    session.add(so)
    await session.flush()

    for ld in line_dicts:
        session.add(SalesOrderLine(sales_order_id=so.id, **ld))

    await session.flush()
    await session.refresh(so)
    repo = SalesOrderRepository(session)
    so = await repo.get_detail(org_id, so.id)  # type: ignore[assignment]

    logger.info("so_created", so_id=so.id, document_no=so.document_no, org_id=org_id)
    return _to_response(so)  # type: ignore[arg-type]


async def update_so(
    session: AsyncSession,
    so_id: int,
    data: SalesOrderUpdate,
    *,
    org_id: int,
    user: User,
) -> SalesOrderDetail:
    repo = SalesOrderRepository(session)
    so = await repo.get_detail(org_id, so_id)
    if so is None:
        raise NotFoundError(message=f"Sales order {so_id} not found.")
    if so.status != SOStatus.DRAFT:
        raise BusinessRuleError(
            message="Only DRAFT sales orders can be edited.",
            error_code="SO_NOT_EDITABLE",
        )

    update_fields: dict = {"updated_by": user.id}
    if data.customer_id is not None:
        update_fields["customer_id"] = data.customer_id
    if data.warehouse_id is not None:
        update_fields["warehouse_id"] = data.warehouse_id
    if data.business_date is not None:
        update_fields["business_date"] = data.business_date
    if data.expected_ship_date is not None:
        update_fields["expected_ship_date"] = data.expected_ship_date
    if data.currency is not None:
        update_fields["currency"] = data.currency
    if data.exchange_rate is not None:
        update_fields["exchange_rate"] = data.exchange_rate.quantize(
            Decimal("0.00000001"), ROUND_HALF_UP
        )
    if data.payment_terms_days is not None:
        update_fields["payment_terms_days"] = data.payment_terms_days
    if data.shipping_address is not None:
        update_fields["shipping_address"] = data.shipping_address
    if data.remarks is not None:
        update_fields["remarks"] = data.remarks

    if data.lines is not None:
        for line in so.lines:
            await session.delete(line)
        await session.flush()

        line_dicts = [_calc_line(ln, idx + 1) for idx, ln in enumerate(data.lines)]
        shipping = (
            data.shipping_amount
            if data.shipping_amount is not None
            else so.shipping_amount
        )
        totals = _calc_totals(line_dicts, shipping)
        update_fields.update(totals)

        exchange_rate = update_fields.get("exchange_rate", so.exchange_rate)
        update_fields["base_currency_amount"] = (
            totals["total_incl_tax"] * exchange_rate
        ).quantize(_TWO, ROUND_HALF_UP)

        for ld in line_dicts:
            session.add(SalesOrderLine(sales_order_id=so.id, **ld))
    elif data.shipping_amount is not None:
        # Shipping changed without line changes — recompute totals using
        # existing lines.
        subtotal = sum((ln.line_total_excl_tax for ln in so.lines), Decimal("0"))
        tax = sum((ln.tax_amount for ln in so.lines), Decimal("0"))
        shipping = data.shipping_amount.quantize(_TWO, ROUND_HALF_UP)
        total = (subtotal + tax + shipping).quantize(_TWO, ROUND_HALF_UP)
        update_fields["shipping_amount"] = shipping
        update_fields["total_incl_tax"] = total
        exchange_rate = update_fields.get("exchange_rate", so.exchange_rate)
        update_fields["base_currency_amount"] = (
            total * exchange_rate
        ).quantize(_TWO, ROUND_HALF_UP)

    for k, v in update_fields.items():
        setattr(so, k, v)
    await session.flush()

    so = await repo.get_detail(org_id, so_id)  # type: ignore[assignment]
    return _to_response(so)  # type: ignore[arg-type]


async def confirm_so(
    session: AsyncSession,
    so_id: int,
    *,
    org_id: int,
    user: User,
) -> SalesOrderDetail:
    repo = SalesOrderRepository(session)
    so = await repo.get_detail(org_id, so_id)
    if so is None:
        raise NotFoundError(message=f"Sales order {so_id} not found.")
    if so.status != SOStatus.DRAFT:
        raise InvalidStatusTransitionError(
            message=f"Cannot confirm a sales order in {so.status.value} status."
        )
    if not so.lines:
        raise BusinessRuleError(
            message="Cannot confirm a sales order with no lines.",
            error_code="SO_NO_LINES",
        )

    now = datetime.now(UTC).replace(tzinfo=None)
    old_status = so.status.value

    # Reserve stock per line. Any failure raises InsufficientStockError and
    # rolls back the entire transaction (Stock + SO).
    for line in so.lines:
        await inventory_svc.apply_reserve(
            session,
            org_id=org_id,
            sku_id=line.sku_id,
            warehouse_id=so.warehouse_id,
            qty=line.qty_ordered,
            source_document_id=so.id,
            source_line_id=line.id,
            actor_user_id=user.id,
        )

    so.status = SOStatus.CONFIRMED
    so.confirmed_at = now
    so.updated_by = user.id
    session.add(so)

    await event_bus.publish(
        DocumentStatusChanged(
            document_type="SO",
            document_id=so.id,
            document_no=so.document_no,
            old_status=old_status,
            new_status=SOStatus.CONFIRMED.value,
            organization_id=org_id,
            actor_user_id=user.id,
        ),
        session,
    )

    await session.flush()
    so = await repo.get_detail(org_id, so_id)  # type: ignore[assignment]
    logger.info("so_confirmed", so_id=so_id, document_no=so.document_no)  # type: ignore[union-attr]
    return _to_response(so)  # type: ignore[arg-type]


async def cancel_so(
    session: AsyncSession,
    so_id: int,
    data: SalesOrderCancel,
    *,
    org_id: int,
    user: User,
) -> SalesOrderDetail:
    repo = SalesOrderRepository(session)
    so = await repo.get_detail(org_id, so_id)
    if so is None:
        raise NotFoundError(message=f"Sales order {so_id} not found.")

    if so.status not in (SOStatus.DRAFT, SOStatus.CONFIRMED):
        raise InvalidStatusTransitionError(
            message=(
                f"Cannot cancel a sales order in {so.status.value} status. "
                "Shipped orders must use the Credit Note flow (Window 12)."
            )
        )

    # CONFIRMED cancellation requires Manager or Admin (Sales role cannot
    # unilaterally release reserved stock).
    if so.status == SOStatus.CONFIRMED:
        user_roles = {r.code for r in user.roles} if user.roles else set()
        allowed = {RoleCode.ADMIN.value, RoleCode.MANAGER.value}
        if not user_roles & allowed:
            raise AuthorizationError(
                message="Only Manager or Admin can cancel a confirmed sales order."
            )

    now = datetime.now(UTC).replace(tzinfo=None)
    old_status = so.status.value
    was_confirmed = so.status == SOStatus.CONFIRMED

    if was_confirmed:
        # Release reserved stock for each remaining-unshipped quantity.
        for line in so.lines:
            remaining = line.qty_ordered - line.qty_shipped
            if remaining > 0:
                await inventory_svc.apply_unreserve(
                    session,
                    org_id=org_id,
                    sku_id=line.sku_id,
                    warehouse_id=so.warehouse_id,
                    qty=remaining,
                    source_document_id=so.id,
                    source_line_id=line.id,
                    actor_user_id=user.id,
                )

    so.status = SOStatus.CANCELLED
    so.cancelled_at = now
    so.cancel_reason = data.cancel_reason
    so.updated_by = user.id
    session.add(so)

    await event_bus.publish(
        DocumentStatusChanged(
            document_type="SO",
            document_id=so.id,
            document_no=so.document_no,
            old_status=old_status,
            new_status=SOStatus.CANCELLED.value,
            organization_id=org_id,
            actor_user_id=user.id,
        ),
        session,
    )

    await session.flush()
    so = await repo.get_detail(org_id, so_id)  # type: ignore[assignment]
    logger.info("so_cancelled", so_id=so_id, reason=data.cancel_reason)
    return _to_response(so)  # type: ignore[arg-type]
