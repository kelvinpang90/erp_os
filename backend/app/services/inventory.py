"""Inventory service — single entry point for all Stock writes.

This module owns:
* Atomic 6-dimension Stock updates (on_hand / reserved / quality_hold /
  available / incoming / in_transit)
* Weighted-average cost recomputation (delegating math to costing.py)
* StockMovement audit-row creation
* Publishing StockMovementOccurred events

Service callers (purchase, sales, transfer, adjustment) MUST go through this
module rather than mutating Stock directly. Window 8 implements
``apply_purchase_in``; Window 10/13 will fill in the other apply_* helpers
(currently raising NotImplementedError so future windows fail fast if a
caller forgets to update the entry point).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Optional

import structlog
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.exceptions import BusinessRuleError, InsufficientStockError
from app.enums import StockMovementSourceType, StockMovementType
from app.events import event_bus
from app.events.types import StockMovementOccurred
from app.models.stock import Stock, StockMovement
from app.services.costing import compute_weighted_average

logger = structlog.get_logger()


def _utc_naive() -> datetime:
    """Current time in UTC stored as naive datetime (matches DB columns)."""
    return datetime.now(UTC).replace(tzinfo=None)


async def _get_or_create_stock(
    session: AsyncSession,
    *,
    org_id: int,
    sku_id: int,
    warehouse_id: int,
) -> Stock:
    """Fetch the Stock row or create a zeroed one."""
    stmt = select(Stock).where(
        Stock.sku_id == sku_id,
        Stock.warehouse_id == warehouse_id,
    )
    result = await session.execute(stmt)
    stock = result.scalar_one_or_none()
    if stock is not None:
        return stock

    stock = Stock(
        organization_id=org_id,
        sku_id=sku_id,
        warehouse_id=warehouse_id,
        on_hand=Decimal("0"),
        reserved=Decimal("0"),
        quality_hold=Decimal("0"),
        incoming=Decimal("0"),
        in_transit=Decimal("0"),
        avg_cost=Decimal("0"),
        last_cost=None,
        initial_on_hand=Decimal("0"),
        initial_avg_cost=Decimal("0"),
    )
    session.add(stock)
    await session.flush()
    await session.refresh(stock)
    return stock


async def apply_purchase_in(
    session: AsyncSession,
    *,
    org_id: int,
    sku_id: int,
    warehouse_id: int,
    qty: Decimal,
    unit_cost: Decimal,
    source_document_id: int,
    source_line_id: Optional[int] = None,
    batch_no: Optional[str] = None,
    expiry_date=None,
    actor_user_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> tuple[Stock, Decimal]:
    """Apply a purchase-in (Goods Receipt) movement to inventory.

    Effects within the current transaction:
    1. Recompute the weighted-average cost for (sku, warehouse).
    2. Atomically update Stock: on_hand += qty, incoming -= qty,
       avg_cost = new_avg, last_cost = unit_cost, version += 1.
    3. Insert one StockMovement audit row.
    4. Publish a StockMovementOccurred event.

    Args:
        qty: Quantity being received (must be > 0).
        unit_cost: Per-unit cost for this receipt (>= 0).
        source_document_id: GoodsReceipt.id.
        source_line_id: GoodsReceiptLine.id.

    Returns:
        Tuple ``(stock, new_avg_cost)`` — the (re-fetched) Stock and the
        freshly-computed weighted-average.

    Raises:
        BusinessRuleError: optimistic-lock conflict (concurrent modification).
        ValueError: qty or unit_cost out of range.
    """
    if qty <= 0:
        raise ValueError("qty must be > 0")
    if unit_cost < 0:
        raise ValueError("unit_cost must be >= 0")

    stock = await _get_or_create_stock(
        session,
        org_id=org_id,
        sku_id=sku_id,
        warehouse_id=warehouse_id,
    )

    # Compute new weighted-average cost using current state.
    new_avg = compute_weighted_average(
        current_qty=stock.on_hand,
        current_avg_cost=stock.avg_cost,
        incoming_qty=qty,
        incoming_unit_cost=unit_cost,
    )

    now = _utc_naive()
    expected_version = stock.version

    # Atomic update — guarded by version (optimistic lock).
    result = await session.execute(
        update(Stock)
        .where(Stock.id == stock.id, Stock.version == expected_version)
        .values(
            on_hand=Stock.on_hand + qty,
            incoming=Stock.incoming - qty,  # release PO-confirmed reservation
            avg_cost=new_avg,
            last_cost=unit_cost,
            last_movement_at=now,
            version=Stock.version + 1,
        )
    )
    if result.rowcount == 0:
        # Row exists but version moved — concurrent modification.
        raise BusinessRuleError(
            message=(
                f"Stock for sku={sku_id} warehouse={warehouse_id} was modified "
                "concurrently. Please retry."
            ),
            error_code="STOCK_CONFLICT",
        )

    # Audit movement row — quantity stored as positive; movement_type encodes
    # direction. avg_cost_after is the freshly-computed weighted average.
    movement = StockMovement(
        organization_id=org_id,
        sku_id=sku_id,
        warehouse_id=warehouse_id,
        movement_type=StockMovementType.PURCHASE_IN,
        quantity=qty,
        unit_cost=unit_cost,
        avg_cost_after=new_avg,
        source_document_type=StockMovementSourceType.GR,
        source_document_id=source_document_id,
        source_line_id=source_line_id,
        batch_no=batch_no,
        expiry_date=expiry_date,
        notes=notes,
        actor_user_id=actor_user_id,
        occurred_at=now,
    )
    session.add(movement)
    await session.flush()

    # Refresh stock so caller sees the post-update state.
    await session.refresh(stock)

    # Publish event — sync handlers run immediately, after-commit handlers
    # (low-stock notification, cache invalidation) queued until commit.
    await event_bus.publish(
        StockMovementOccurred(
            organization_id=org_id,
            sku_id=sku_id,
            warehouse_id=warehouse_id,
            movement_type=StockMovementType.PURCHASE_IN.value,
            quantity=qty,
            source_document_type=StockMovementSourceType.GR.value,
            source_document_id=source_document_id,
        ),
        session,
    )

    logger.info(
        "stock_purchase_in_applied",
        org_id=org_id,
        sku_id=sku_id,
        warehouse_id=warehouse_id,
        qty=str(qty),
        unit_cost=str(unit_cost),
        new_avg_cost=str(new_avg),
        gr_id=source_document_id,
    )

    return stock, new_avg


# ── Window 10: Sales reservation + outbound ──────────────────────────────────


async def apply_reserve(
    session: AsyncSession,
    *,
    org_id: int,
    sku_id: int,
    warehouse_id: int,
    qty: Decimal,
    source_document_id: int,
    source_line_id: Optional[int] = None,
    actor_user_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> Stock:
    """Reserve stock for a confirmed Sales Order line.

    Effects within the current transaction:
    1. Atomically increment Stock.reserved if available >= qty
       (UPDATE ... WHERE on_hand - reserved - quality_hold >= qty).
    2. Insert one StockMovement audit row (movement_type=RESERVE).
    3. Publish a StockMovementOccurred event.

    Raises:
        InsufficientStockError: when available < qty.
        ValueError: qty out of range.
    """
    if qty <= 0:
        raise ValueError("qty must be > 0")

    stock = await _get_or_create_stock(
        session,
        org_id=org_id,
        sku_id=sku_id,
        warehouse_id=warehouse_id,
    )

    now = _utc_naive()

    # Atomic reservation: WHERE clause expands `available` since it's a
    # Computed column (not a physical column we can reference directly in DML).
    result = await session.execute(
        update(Stock)
        .where(
            Stock.id == stock.id,
            Stock.on_hand - Stock.reserved - Stock.quality_hold >= qty,
        )
        .values(
            reserved=Stock.reserved + qty,
            last_movement_at=now,
            version=Stock.version + 1,
        )
    )
    if result.rowcount == 0:
        raise InsufficientStockError(
            message=(
                f"Insufficient stock for sku={sku_id} warehouse={warehouse_id}: "
                f"requested {qty}, available {stock.on_hand - stock.reserved - stock.quality_hold}."
            ),
            detail={
                "sku_id": sku_id,
                "warehouse_id": warehouse_id,
                "requested": str(qty),
            },
        )

    movement = StockMovement(
        organization_id=org_id,
        sku_id=sku_id,
        warehouse_id=warehouse_id,
        movement_type=StockMovementType.RESERVE,
        quantity=qty,
        unit_cost=None,
        avg_cost_after=stock.avg_cost,
        source_document_type=StockMovementSourceType.SO,
        source_document_id=source_document_id,
        source_line_id=source_line_id,
        notes=notes,
        actor_user_id=actor_user_id,
        occurred_at=now,
    )
    session.add(movement)
    await session.flush()
    await session.refresh(stock)

    await event_bus.publish(
        StockMovementOccurred(
            organization_id=org_id,
            sku_id=sku_id,
            warehouse_id=warehouse_id,
            movement_type=StockMovementType.RESERVE.value,
            quantity=qty,
            source_document_type=StockMovementSourceType.SO.value,
            source_document_id=source_document_id,
        ),
        session,
    )

    logger.info(
        "stock_reserved",
        org_id=org_id,
        sku_id=sku_id,
        warehouse_id=warehouse_id,
        qty=str(qty),
        so_id=source_document_id,
    )
    return stock


async def apply_unreserve(
    session: AsyncSession,
    *,
    org_id: int,
    sku_id: int,
    warehouse_id: int,
    qty: Decimal,
    source_document_id: int,
    source_line_id: Optional[int] = None,
    actor_user_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> Stock:
    """Release a reservation (Sales Order cancellation).

    Effects:
    1. Atomically decrement Stock.reserved (guarded so reserved >= qty).
    2. Insert one StockMovement audit row (movement_type=UNRESERVE).
    3. Publish StockMovementOccurred.
    """
    if qty <= 0:
        raise ValueError("qty must be > 0")

    stmt = select(Stock).where(
        Stock.sku_id == sku_id,
        Stock.warehouse_id == warehouse_id,
    )
    result = await session.execute(stmt)
    stock = result.scalar_one_or_none()
    if stock is None:
        raise BusinessRuleError(
            message=f"No stock row found for sku={sku_id} warehouse={warehouse_id}.",
            error_code="STOCK_MISSING",
        )

    now = _utc_naive()

    result = await session.execute(
        update(Stock)
        .where(Stock.id == stock.id, Stock.reserved >= qty)
        .values(
            reserved=Stock.reserved - qty,
            last_movement_at=now,
            version=Stock.version + 1,
        )
    )
    if result.rowcount == 0:
        raise BusinessRuleError(
            message=(
                f"Cannot unreserve {qty} from sku={sku_id} warehouse={warehouse_id}: "
                f"current reserved is {stock.reserved}."
            ),
            error_code="UNRESERVE_UNDERFLOW",
        )

    movement = StockMovement(
        organization_id=org_id,
        sku_id=sku_id,
        warehouse_id=warehouse_id,
        movement_type=StockMovementType.UNRESERVE,
        quantity=qty,
        unit_cost=None,
        avg_cost_after=stock.avg_cost,
        source_document_type=StockMovementSourceType.SO,
        source_document_id=source_document_id,
        source_line_id=source_line_id,
        notes=notes,
        actor_user_id=actor_user_id,
        occurred_at=now,
    )
    session.add(movement)
    await session.flush()
    await session.refresh(stock)

    await event_bus.publish(
        StockMovementOccurred(
            organization_id=org_id,
            sku_id=sku_id,
            warehouse_id=warehouse_id,
            movement_type=StockMovementType.UNRESERVE.value,
            quantity=qty,
            source_document_type=StockMovementSourceType.SO.value,
            source_document_id=source_document_id,
        ),
        session,
    )

    logger.info(
        "stock_unreserved",
        org_id=org_id,
        sku_id=sku_id,
        warehouse_id=warehouse_id,
        qty=str(qty),
        so_id=source_document_id,
    )
    return stock


async def apply_sales_out(
    session: AsyncSession,
    *,
    org_id: int,
    sku_id: int,
    warehouse_id: int,
    qty: Decimal,
    source_document_id: int,
    source_line_id: Optional[int] = None,
    batch_no: Optional[str] = None,
    expiry_date=None,
    actor_user_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> tuple[Stock, Decimal]:
    """Apply a sales-out (Delivery Order) movement to inventory.

    Effects within the current transaction:
    1. Atomically update Stock: on_hand -= qty, reserved -= qty,
       version += 1 (guarded so both have enough capacity).
    2. avg_cost is NOT recomputed (outbound moves do not affect WAC).
    3. Insert one StockMovement audit row (SALES_OUT).
    4. Publish StockMovementOccurred event.

    Returns:
        Tuple ``(stock, current_avg_cost)`` — the snapshot avg_cost the caller
        should write to ``SalesOrderLine.snapshot_avg_cost`` (first shipment
        only) for future Credit Note rollback (Window 12).

    Raises:
        BusinessRuleError: optimistic-lock conflict OR insufficient on_hand /
            reserved (concurrent modification or programming error).
        ValueError: qty out of range.
    """
    if qty <= 0:
        raise ValueError("qty must be > 0")

    stmt = select(Stock).where(
        Stock.sku_id == sku_id,
        Stock.warehouse_id == warehouse_id,
    )
    result = await session.execute(stmt)
    stock = result.scalar_one_or_none()
    if stock is None:
        raise BusinessRuleError(
            message=f"No stock row found for sku={sku_id} warehouse={warehouse_id}.",
            error_code="STOCK_MISSING",
        )

    now = _utc_naive()
    expected_version = stock.version
    snapshot_avg_cost = stock.avg_cost

    # Atomic update — guarded by version (optimistic lock) AND quantity
    # invariants. Both reserved and on_hand must have enough.
    result = await session.execute(
        update(Stock)
        .where(
            Stock.id == stock.id,
            Stock.version == expected_version,
            Stock.reserved >= qty,
            Stock.on_hand >= qty,
        )
        .values(
            on_hand=Stock.on_hand - qty,
            reserved=Stock.reserved - qty,
            last_movement_at=now,
            version=Stock.version + 1,
        )
    )
    if result.rowcount == 0:
        raise BusinessRuleError(
            message=(
                f"Cannot ship {qty} of sku={sku_id} from warehouse={warehouse_id}: "
                "stock was modified concurrently or insufficient on_hand/reserved."
            ),
            error_code="STOCK_CONFLICT",
        )

    movement = StockMovement(
        organization_id=org_id,
        sku_id=sku_id,
        warehouse_id=warehouse_id,
        movement_type=StockMovementType.SALES_OUT,
        quantity=qty,
        unit_cost=snapshot_avg_cost,  # COGS at the moment of shipment
        avg_cost_after=snapshot_avg_cost,  # WAC unchanged on outbound
        source_document_type=StockMovementSourceType.DO,
        source_document_id=source_document_id,
        source_line_id=source_line_id,
        batch_no=batch_no,
        expiry_date=expiry_date,
        notes=notes,
        actor_user_id=actor_user_id,
        occurred_at=now,
    )
    session.add(movement)
    await session.flush()
    await session.refresh(stock)

    await event_bus.publish(
        StockMovementOccurred(
            organization_id=org_id,
            sku_id=sku_id,
            warehouse_id=warehouse_id,
            movement_type=StockMovementType.SALES_OUT.value,
            quantity=qty,
            source_document_type=StockMovementSourceType.DO.value,
            source_document_id=source_document_id,
        ),
        session,
    )

    logger.info(
        "stock_sales_out_applied",
        org_id=org_id,
        sku_id=sku_id,
        warehouse_id=warehouse_id,
        qty=str(qty),
        avg_cost=str(snapshot_avg_cost),
        do_id=source_document_id,
    )

    return stock, snapshot_avg_cost


# ── Window 12: Sales return (Credit Note) ────────────────────────────────────


async def apply_sales_return(
    session: AsyncSession,
    *,
    org_id: int,
    sku_id: int,
    warehouse_id: int,
    qty: Decimal,
    unit_cost: Decimal,
    source_document_id: int,
    source_line_id: Optional[int] = None,
    batch_no: Optional[str] = None,
    expiry_date=None,
    actor_user_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> tuple[Stock, Decimal]:
    """Apply a sales-return (Credit Note) inbound to inventory.

    Cloned from apply_purchase_in but with three deliberate differences:

    1. ``incoming`` is NOT decremented — sales returns never went through a PO,
       so there's no Incoming reservation to release.
    2. ``movement_type`` is ``SALES_RETURN`` (not ``PURCHASE_IN``) so the audit
       trail correctly distinguishes returns from receipts.
    3. ``source_document_type`` is ``CN`` (not ``GR``).

    The ``unit_cost`` should be the SOLine.snapshot_avg_cost captured at first
    shipment so the weighted-average doesn't get polluted by the return — see
    Window 10's snapshot_avg_cost design.

    Effects within the current transaction:
    1. Recompute the weighted-average cost for (sku, warehouse).
    2. Atomically update Stock: on_hand += qty, avg_cost = new_avg,
       last_cost = unit_cost, version += 1.
    3. Insert one StockMovement audit row (SALES_RETURN / CN).
    4. Publish a StockMovementOccurred event.

    Args:
        qty: Return quantity (must be > 0).
        unit_cost: Snapshot avg_cost from the SOLine (>= 0).
        source_document_id: CreditNote.id.
        source_line_id: CreditNoteLine.id.

    Returns:
        Tuple ``(stock, new_avg_cost)``.

    Raises:
        BusinessRuleError: optimistic-lock conflict.
        ValueError: qty or unit_cost out of range.
    """
    if qty <= 0:
        raise ValueError("qty must be > 0")
    if unit_cost < 0:
        raise ValueError("unit_cost must be >= 0")

    stock = await _get_or_create_stock(
        session,
        org_id=org_id,
        sku_id=sku_id,
        warehouse_id=warehouse_id,
    )

    new_avg = compute_weighted_average(
        current_qty=stock.on_hand,
        current_avg_cost=stock.avg_cost,
        incoming_qty=qty,
        incoming_unit_cost=unit_cost,
    )

    now = _utc_naive()
    expected_version = stock.version

    result = await session.execute(
        update(Stock)
        .where(Stock.id == stock.id, Stock.version == expected_version)
        .values(
            on_hand=Stock.on_hand + qty,
            # incoming intentionally untouched — see docstring.
            avg_cost=new_avg,
            last_cost=unit_cost,
            last_movement_at=now,
            version=Stock.version + 1,
        )
    )
    if result.rowcount == 0:
        raise BusinessRuleError(
            message=(
                f"Stock for sku={sku_id} warehouse={warehouse_id} was modified "
                "concurrently. Please retry."
            ),
            error_code="STOCK_CONFLICT",
        )

    movement = StockMovement(
        organization_id=org_id,
        sku_id=sku_id,
        warehouse_id=warehouse_id,
        movement_type=StockMovementType.SALES_RETURN,
        quantity=qty,
        unit_cost=unit_cost,
        avg_cost_after=new_avg,
        source_document_type=StockMovementSourceType.CN,
        source_document_id=source_document_id,
        source_line_id=source_line_id,
        batch_no=batch_no,
        expiry_date=expiry_date,
        notes=notes,
        actor_user_id=actor_user_id,
        occurred_at=now,
    )
    session.add(movement)
    await session.flush()
    await session.refresh(stock)

    await event_bus.publish(
        StockMovementOccurred(
            organization_id=org_id,
            sku_id=sku_id,
            warehouse_id=warehouse_id,
            movement_type=StockMovementType.SALES_RETURN.value,
            quantity=qty,
            source_document_type=StockMovementSourceType.CN.value,
            source_document_id=source_document_id,
        ),
        session,
    )

    logger.info(
        "stock_sales_return_applied",
        org_id=org_id,
        sku_id=sku_id,
        warehouse_id=warehouse_id,
        qty=str(qty),
        unit_cost=str(unit_cost),
        new_avg_cost=str(new_avg),
        cn_id=source_document_id,
    )

    return stock, new_avg


# ── Reserved for future windows ──────────────────────────────────────────────


async def apply_transfer_out(*args, **kwargs):  # pragma: no cover — W13
    """Reserved for Window 13 (Stock Transfer)."""
    raise NotImplementedError("apply_transfer_out is implemented in Window 13.")


async def apply_transfer_in(*args, **kwargs):  # pragma: no cover — W13
    """Reserved for Window 13 (Stock Transfer)."""
    raise NotImplementedError("apply_transfer_in is implemented in Window 13.")


async def apply_adjustment(*args, **kwargs):  # pragma: no cover — W13
    """Reserved for Window 13 (Stock Adjustment)."""
    raise NotImplementedError("apply_adjustment is implemented in Window 13.")
