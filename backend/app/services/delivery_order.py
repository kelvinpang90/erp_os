"""DeliveryOrder service — single-step ship-and-apply flow.

Flow (Window 10):
1. Validate SO is in CONFIRMED or PARTIAL_SHIPPED state.
2. For each DO line, validate qty_shipped ≤ remaining (no over-shipment).
3. Persist DeliveryOrder + DeliveryOrderLine rows.
4. For each line call inventory.apply_sales_out (Stock 6-dim update +
   StockMovement audit + StockMovementOccurred event). Capture the
   snapshot_avg_cost returned and write it to the SO line ON FIRST SHIPMENT
   ONLY (idempotent for partial shipping).
5. Accumulate qty_shipped on each SO line.
6. Re-evaluate SO status:
       all lines fully shipped → FULLY_SHIPPED + set fully_shipped_at
       at least one partial    → PARTIAL_SHIPPED
   Publish DocumentStatusChanged on transition.

Note: DO cancellation / reversal is deferred to Window 12 (Credit Note).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BusinessRuleError,
    InvalidStatusTransitionError,
    NotFoundError,
    ValidationError,
)
from app.enums import SOStatus
from app.events import event_bus
from app.events.types import DocumentStatusChanged
from app.models.organization import User
from app.models.sales import (
    DeliveryOrder,
    DeliveryOrderLine,
    SalesOrder,
    SalesOrderLine,
)
from app.repositories.delivery_order import DeliveryOrderRepository
from app.repositories.sales_order import SalesOrderRepository
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.delivery_order import (
    DeliveryOrderCreate,
    DeliveryOrderDetail,
    DeliveryOrderLineResponse,
    DeliveryOrderResponse,
)
from app.services import inventory as inventory_svc
from app.services.sequence import next_document_no

logger = structlog.get_logger()

_FOUR = Decimal("0.0001")


# ── Helpers ───────────────────────────────────────────────────────────────────


def _to_response(do: DeliveryOrder) -> DeliveryOrderDetail:
    line_resps: list[DeliveryOrderLineResponse] = []
    for ln in do.lines or []:
        resp = DeliveryOrderLineResponse.model_validate(ln)
        if ln.sku is not None:
            resp.sku_code = ln.sku.code
            resp.sku_name = ln.sku.name
        if ln.sales_order_line is not None:
            resp.qty_ordered = ln.sales_order_line.qty_ordered
            # qty_already_shipped is the SO line accumulator AFTER this DO
            # was applied — UI shows "X of Y shipped".
            resp.qty_already_shipped = ln.sales_order_line.qty_shipped
        line_resps.append(resp)
    detail = DeliveryOrderDetail.model_validate(do)
    detail.lines = line_resps
    if do.sales_order is not None:
        detail.sales_order_no = do.sales_order.document_no
    if do.warehouse is not None:
        detail.warehouse_name = do.warehouse.name
    if do.deliverer is not None:
        detail.delivered_by_name = do.deliverer.full_name
    return detail


def _so_lines_by_id(so: SalesOrder) -> dict[int, SalesOrderLine]:
    return {ln.id: ln for ln in (so.lines or [])}


# ── Public API ───────────────────────────────────────────────────────────────


async def create_do(
    session: AsyncSession,
    data: DeliveryOrderCreate,
    *,
    org_id: int,
    user: User,
) -> DeliveryOrderDetail:
    """Create a DeliveryOrder and apply all stock effects in one transaction."""
    so_repo = SalesOrderRepository(session)
    so = await so_repo.get_detail(org_id, data.sales_order_id)
    if so is None:
        raise NotFoundError(
            message=f"Sales order {data.sales_order_id} not found.",
            error_code="SO_NOT_FOUND",
        )

    if so.status not in (SOStatus.CONFIRMED, SOStatus.PARTIAL_SHIPPED):
        raise InvalidStatusTransitionError(
            message=(
                f"Cannot create delivery order: SO is in {so.status.value} status. "
                "Only CONFIRMED or PARTIAL_SHIPPED sales orders may be shipped."
            ),
            error_code="SO_NOT_SHIPPABLE",
        )

    so_line_index = _so_lines_by_id(so)
    seen_line_ids: set[int] = set()

    for in_line in data.lines:
        if in_line.sales_order_line_id not in so_line_index:
            raise ValidationError(
                message=(
                    f"SO line {in_line.sales_order_line_id} does not belong "
                    f"to sales order {so.id}."
                ),
                error_code="DO_LINE_INVALID_SO_LINE",
            )
        if in_line.sales_order_line_id in seen_line_ids:
            raise ValidationError(
                message=(
                    f"Duplicate SO line {in_line.sales_order_line_id} in "
                    "delivery order input."
                ),
                error_code="DO_LINE_DUPLICATE",
            )
        seen_line_ids.add(in_line.sales_order_line_id)

        so_line = so_line_index[in_line.sales_order_line_id]
        remaining = so_line.qty_ordered - so_line.qty_shipped
        if remaining <= 0:
            raise BusinessRuleError(
                message=(
                    f"SO line {so_line.line_no} (sku={so_line.sku_id}) is already "
                    f"fully shipped (ordered={so_line.qty_ordered}, "
                    f"shipped={so_line.qty_shipped})."
                ),
                error_code="DO_LINE_ALREADY_FULL",
            )
        if in_line.qty_shipped > remaining:
            raise BusinessRuleError(
                message=(
                    f"qty_shipped {in_line.qty_shipped} exceeds remaining "
                    f"{remaining} for SO line {so_line.line_no}."
                ),
                error_code="DO_OVER_SHIPMENT",
            )

    document_no = await next_document_no(session, "DO", org_id)
    now = datetime.now(UTC).replace(tzinfo=None)

    do = DeliveryOrder(
        organization_id=org_id,
        document_no=document_no,
        sales_order_id=so.id,
        warehouse_id=so.warehouse_id,
        delivery_date=data.delivery_date,
        shipping_method=data.shipping_method,
        tracking_no=data.tracking_no,
        delivered_by=data.delivered_by or user.id,
        remarks=data.remarks,
        created_by=user.id,
    )
    session.add(do)
    await session.flush()

    # Persist DO lines + apply stock effects + accumulate qty on SO lines.
    for idx, in_line in enumerate(data.lines, start=1):
        so_line = so_line_index[in_line.sales_order_line_id]
        qty = in_line.qty_shipped.quantize(_FOUR, rounding=ROUND_HALF_UP)

        do_line = DeliveryOrderLine(
            delivery_order_id=do.id,
            sales_order_line_id=so_line.id,
            line_no=idx,
            sku_id=so_line.sku_id,
            uom_id=so_line.uom_id,
            qty_shipped=qty,
            batch_no=in_line.batch_no,
            expiry_date=in_line.expiry_date,
            serial_no=in_line.serial_no,
        )
        session.add(do_line)
        await session.flush()

        # Apply 6-dim stock update + StockMovement audit.
        # Returns the avg_cost at the moment of shipment (used as COGS basis).
        _stock, snapshot_avg_cost = await inventory_svc.apply_sales_out(
            session,
            org_id=org_id,
            sku_id=so_line.sku_id,
            warehouse_id=so.warehouse_id,
            qty=qty,
            source_document_id=do.id,
            source_line_id=do_line.id,
            batch_no=in_line.batch_no,
            expiry_date=in_line.expiry_date,
            actor_user_id=user.id,
        )

        # First-shipment-only: capture the snapshot for Credit Note rollback
        # (Window 12). Subsequent partial shipments preserve the original.
        if so_line.snapshot_avg_cost is None:
            so_line.snapshot_avg_cost = snapshot_avg_cost

        so_line.qty_shipped = so_line.qty_shipped + qty

    # ── SO status transition ─────────────────────────────────────────────────
    fully_shipped = all(
        ln.qty_shipped >= ln.qty_ordered for ln in so.lines or []
    )
    any_shipped = any(
        ln.qty_shipped > Decimal("0") for ln in so.lines or []
    )

    new_status: Optional[SOStatus] = None
    if fully_shipped:
        new_status = SOStatus.FULLY_SHIPPED
    elif any_shipped:
        new_status = SOStatus.PARTIAL_SHIPPED

    if new_status is not None and new_status != so.status:
        old_status = so.status.value
        so.status = new_status
        if new_status == SOStatus.FULLY_SHIPPED:
            so.fully_shipped_at = now
        so.updated_by = user.id
        session.add(so)
        await event_bus.publish(
            DocumentStatusChanged(
                document_type="SO",
                document_id=so.id,
                document_no=so.document_no,
                old_status=old_status,
                new_status=new_status.value,
                organization_id=org_id,
                actor_user_id=user.id,
            ),
            session,
        )
        logger.info(
            "so_status_advanced_by_do",
            so_id=so.id,
            document_no=so.document_no,
            old_status=old_status,
            new_status=new_status.value,
            do_document_no=document_no,
        )

    await session.flush()
    do_repo = DeliveryOrderRepository(session)
    do_full = await do_repo.get_detail(org_id, do.id)
    if do_full is None:  # pragma: no cover — defensive
        raise NotFoundError(message=f"Delivery order {do.id} not found after creation.")

    logger.info(
        "do_created",
        do_id=do_full.id,
        document_no=do_full.document_no,
        so_id=so.id,
        org_id=org_id,
        line_count=len(data.lines),
    )
    return _to_response(do_full)


async def get_do(
    session: AsyncSession,
    do_id: int,
    *,
    org_id: int,
) -> DeliveryOrderDetail:
    repo = DeliveryOrderRepository(session)
    do = await repo.get_detail(org_id, do_id)
    if do is None:
        raise NotFoundError(
            message=f"Delivery order {do_id} not found.",
            error_code="DO_NOT_FOUND",
        )
    return _to_response(do)


async def list_dos(
    session: AsyncSession,
    pagination: PaginationParams,
    *,
    org_id: int,
    sales_order_id: Optional[int] = None,
    warehouse_id: Optional[int] = None,
    search: Optional[str] = None,
) -> PaginatedResponse[DeliveryOrderResponse]:
    repo = DeliveryOrderRepository(session)
    items, total = await repo.list_with_filters(
        org_id,
        sales_order_id=sales_order_id,
        warehouse_id=warehouse_id,
        search=search,
        limit=pagination.page_size,
        offset=pagination.offset,
    )
    responses = []
    for do in items:
        resp = DeliveryOrderResponse.model_validate(do)
        if do.sales_order is not None:
            resp.sales_order_no = do.sales_order.document_no
        responses.append(resp)
    return PaginatedResponse[DeliveryOrderResponse].build(
        items=responses,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )
