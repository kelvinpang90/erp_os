"""GoodsReceipt service — single-step receive-and-apply flow.

Flow (Window 8):
1. Validate PO is in CONFIRMED or PARTIAL_RECEIVED state.
2. For each GR line, validate qty_received against remaining + tolerance
   (env GR_OVER_RECEIPT_TOLERANCE, default 5%).
3. Persist GoodsReceipt + GoodsReceiptLine rows.
4. Accumulate qty_received on each PO line.
5. For each line call inventory.apply_purchase_in (Stock 6-dim update +
   StockMovement audit + StockMovementOccurred event).
6. Re-evaluate PO status:
       all lines fully received → FULLY_RECEIVED
       at least one partial     → PARTIAL_RECEIVED
   Publish DocumentStatusChanged on transition.

Note: GR cancellation / reversal is deferred to Window 13.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    BusinessRuleError,
    InvalidStatusTransitionError,
    NotFoundError,
    ValidationError,
)
from app.enums import POStatus
from app.events import event_bus
from app.events.types import DocumentStatusChanged
from app.models.organization import User
from app.models.purchase import (
    GoodsReceipt,
    GoodsReceiptLine,
    PurchaseOrder,
    PurchaseOrderLine,
)
from app.repositories.goods_receipt import GoodsReceiptRepository
from app.repositories.purchase_order import PurchaseOrderRepository
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.goods_receipt import (
    GoodsReceiptCreate,
    GoodsReceiptDetail,
    GoodsReceiptLineCreate,
    GoodsReceiptLineResponse,
    GoodsReceiptResponse,
)
from app.services import inventory as inventory_svc
from app.services.sequence import next_document_no

logger = structlog.get_logger()

_FOUR = Decimal("0.0001")


# ── Helpers ───────────────────────────────────────────────────────────────────


def _to_response(gr: GoodsReceipt) -> GoodsReceiptDetail:
    """Build a GoodsReceiptDetail (including lines) from an ORM row."""
    line_resps: list[GoodsReceiptLineResponse] = []
    for ln in gr.lines or []:
        resp = GoodsReceiptLineResponse.model_validate(ln)
        if ln.sku is not None:
            resp.sku_code = ln.sku.code
            resp.sku_name = ln.sku.name
        if ln.purchase_order_line is not None:
            resp.qty_ordered = ln.purchase_order_line.qty_ordered
            # qty_already_received reflects the POL accumulator AFTER this GR
            # was applied. We expose it as the post-update total so the UI
            # can show "X of Y received" without an extra round trip.
            resp.qty_already_received = ln.purchase_order_line.qty_received
        line_resps.append(resp)
    detail = GoodsReceiptDetail.model_validate(gr)
    detail.lines = line_resps
    if gr.purchase_order is not None:
        detail.purchase_order_no = gr.purchase_order.document_no
    return detail


def _check_over_receipt(
    line_in: GoodsReceiptLineCreate,
    po_line: PurchaseOrderLine,
) -> None:
    """Raise BusinessRuleError if qty_received exceeds tolerance allowance."""
    remaining = po_line.qty_ordered - po_line.qty_received
    if remaining <= 0:
        raise BusinessRuleError(
            message=(
                f"PO line {po_line.line_no} (sku={po_line.sku_id}) is already "
                f"fully received (ordered={po_line.qty_ordered}, "
                f"received={po_line.qty_received})."
            ),
            error_code="GR_LINE_ALREADY_FULL",
        )

    tolerance = Decimal(settings.GR_OVER_RECEIPT_TOLERANCE)
    max_allowed = (remaining * (Decimal("1") + tolerance)).quantize(
        _FOUR, rounding=ROUND_HALF_UP
    )
    if line_in.qty_received > max_allowed:
        pct = (tolerance * Decimal("100")).quantize(_FOUR, rounding=ROUND_HALF_UP)
        raise BusinessRuleError(
            message=(
                f"qty_received {line_in.qty_received} exceeds maximum allowed "
                f"{max_allowed} for PO line {po_line.line_no} "
                f"(remaining {remaining} + {pct.normalize()}% tolerance)."
            ),
            error_code="GR_OVER_RECEIPT_EXCEEDED",
        )


def _po_lines_by_id(po: PurchaseOrder) -> dict[int, PurchaseOrderLine]:
    return {ln.id: ln for ln in (po.lines or [])}


# ── Public API ───────────────────────────────────────────────────────────────


async def create_gr(
    session: AsyncSession,
    data: GoodsReceiptCreate,
    *,
    org_id: int,
    user: User,
) -> GoodsReceiptDetail:
    """Create a GoodsReceipt and apply all stock effects in one transaction."""
    po_repo = PurchaseOrderRepository(session)
    po = await po_repo.get_detail(org_id, data.purchase_order_id)
    if po is None:
        raise NotFoundError(
            message=f"Purchase order {data.purchase_order_id} not found.",
            error_code="PO_NOT_FOUND",
        )

    if po.status not in (POStatus.CONFIRMED, POStatus.PARTIAL_RECEIVED):
        raise InvalidStatusTransitionError(
            message=(
                f"Cannot create goods receipt: PO is in {po.status.value} status. "
                "Only CONFIRMED or PARTIAL_RECEIVED purchase orders may be received."
            ),
            error_code="PO_NOT_RECEIVABLE",
        )

    # Map PO lines for fast lookup + validate every input line refers to this PO.
    po_line_index = _po_lines_by_id(po)
    seen_line_ids: set[int] = set()

    for in_line in data.lines:
        if in_line.purchase_order_line_id not in po_line_index:
            raise ValidationError(
                message=(
                    f"PO line {in_line.purchase_order_line_id} does not belong "
                    f"to purchase order {po.id}."
                ),
                error_code="GR_LINE_INVALID_PO_LINE",
            )
        if in_line.purchase_order_line_id in seen_line_ids:
            raise ValidationError(
                message=(
                    f"Duplicate PO line {in_line.purchase_order_line_id} in "
                    "goods receipt input."
                ),
                error_code="GR_LINE_DUPLICATE",
            )
        seen_line_ids.add(in_line.purchase_order_line_id)
        _check_over_receipt(in_line, po_line_index[in_line.purchase_order_line_id])

    # Generate GR document number atomically.
    document_no = await next_document_no(session, "GR", org_id)
    now = datetime.now(UTC).replace(tzinfo=None)

    gr = GoodsReceipt(
        organization_id=org_id,
        document_no=document_no,
        purchase_order_id=po.id,
        warehouse_id=po.warehouse_id,
        receipt_date=data.receipt_date,
        delivery_note_no=data.delivery_note_no,
        received_by=data.received_by or user.id,
        remarks=data.remarks,
        created_by=user.id,
    )
    session.add(gr)
    await session.flush()

    # Persist GR lines + accumulate qty on PO lines + apply stock effects.
    for idx, in_line in enumerate(data.lines, start=1):
        po_line = po_line_index[in_line.purchase_order_line_id]
        unit_cost = in_line.unit_cost
        if unit_cost is None:
            unit_cost = po_line.unit_price_excl_tax
        unit_cost = unit_cost.quantize(_FOUR, rounding=ROUND_HALF_UP)
        qty = in_line.qty_received.quantize(_FOUR, rounding=ROUND_HALF_UP)

        gr_line = GoodsReceiptLine(
            goods_receipt_id=gr.id,
            purchase_order_line_id=po_line.id,
            line_no=idx,
            sku_id=po_line.sku_id,
            uom_id=po_line.uom_id,
            qty_received=qty,
            unit_cost=unit_cost,
            batch_no=in_line.batch_no,
            expiry_date=in_line.expiry_date,
            remarks=in_line.remarks,
        )
        session.add(gr_line)
        await session.flush()

        # Accumulate received qty on the PO line (we already validated it is
        # within tolerance — no further race protection needed here because
        # the calling transaction is serialized by the GR creation flow).
        po_line.qty_received = po_line.qty_received + qty

        # Apply 6-dim stock update + cost recompute + StockMovement audit.
        await inventory_svc.apply_purchase_in(
            session,
            org_id=org_id,
            sku_id=po_line.sku_id,
            warehouse_id=po.warehouse_id,
            qty=qty,
            unit_cost=unit_cost,
            source_document_id=gr.id,
            source_line_id=gr_line.id,
            batch_no=in_line.batch_no,
            expiry_date=in_line.expiry_date,
            actor_user_id=user.id,
        )

    # ── PO status transition ──────────────────────────────────────────────
    # After accumulating qty_received on each line, decide the new PO status.
    fully_received = all(
        ln.qty_received >= ln.qty_ordered for ln in po.lines or []
    )
    any_received = any(
        ln.qty_received > Decimal("0") for ln in po.lines or []
    )

    new_status: Optional[POStatus] = None
    if fully_received:
        new_status = POStatus.FULLY_RECEIVED
    elif any_received:
        new_status = POStatus.PARTIAL_RECEIVED

    if new_status is not None and new_status != po.status:
        old_status = po.status.value
        po.status = new_status
        po.updated_by = user.id
        session.add(po)
        await event_bus.publish(
            DocumentStatusChanged(
                document_type="PO",
                document_id=po.id,
                document_no=po.document_no,
                old_status=old_status,
                new_status=new_status.value,
                organization_id=org_id,
                actor_user_id=user.id,
            ),
            session,
        )
        logger.info(
            "po_status_advanced_by_gr",
            po_id=po.id,
            document_no=po.document_no,
            old_status=old_status,
            new_status=new_status.value,
            gr_document_no=document_no,
        )

    await session.flush()
    gr_repo = GoodsReceiptRepository(session)
    gr_full = await gr_repo.get_detail(org_id, gr.id)
    if gr_full is None:  # pragma: no cover — defensive
        raise NotFoundError(message=f"Goods receipt {gr.id} not found after creation.")

    logger.info(
        "gr_created",
        gr_id=gr_full.id,
        document_no=gr_full.document_no,
        po_id=po.id,
        org_id=org_id,
        line_count=len(data.lines),
    )
    return _to_response(gr_full)


async def get_gr(
    session: AsyncSession,
    gr_id: int,
    *,
    org_id: int,
) -> GoodsReceiptDetail:
    repo = GoodsReceiptRepository(session)
    gr = await repo.get_detail(org_id, gr_id)
    if gr is None:
        raise NotFoundError(
            message=f"Goods receipt {gr_id} not found.",
            error_code="GR_NOT_FOUND",
        )
    return _to_response(gr)


async def list_grs(
    session: AsyncSession,
    pagination: PaginationParams,
    *,
    org_id: int,
    purchase_order_id: Optional[int] = None,
    warehouse_id: Optional[int] = None,
    search: Optional[str] = None,
) -> PaginatedResponse[GoodsReceiptResponse]:
    repo = GoodsReceiptRepository(session)
    items, total = await repo.list_with_filters(
        org_id,
        purchase_order_id=purchase_order_id,
        warehouse_id=warehouse_id,
        search=search,
        limit=pagination.page_size,
        offset=pagination.offset,
    )
    responses = []
    for gr in items:
        resp = GoodsReceiptResponse.model_validate(gr)
        if gr.purchase_order is not None:
            resp.purchase_order_no = gr.purchase_order.document_no
        responses.append(resp)
    return PaginatedResponse[GoodsReceiptResponse].build(
        items=responses,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )
