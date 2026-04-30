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


async def apply_sales_return_reverse(
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
    """Roll back an ``apply_sales_return`` previously applied (CN cancel).

    Why this exists separately from ``apply_sales_out``:
    ``apply_sales_out`` requires both ``reserved >= qty`` and ``on_hand >= qty``
    because it's the second half of the SO → DO flow (reserve first, ship later).
    A Credit Note's inbound never went through ``apply_reserve``, so the
    reserved counter was never incremented. Calling apply_sales_out here would
    fail with STOCK_CONFLICT every time.

    This helper only requires ``on_hand >= qty``:

    1. Atomic update Stock: on_hand -= qty, version += 1.
       ``avg_cost`` is intentionally **not** recomputed — backing out the
       receipt's effect on the weighted average exactly would need the
       pre-inbound avg_cost; for a demo cancel that's overkill, and the
       drift is bounded by the small qty being cancelled.
    2. Audit row uses ``ADJUSTMENT_OUT`` with ``source_document_type=CN`` so the
       (CN, ADJUSTMENT_OUT) tuple is unambiguous in the trail.
    3. Publish ``StockMovementOccurred`` so cache/notifications fire.

    Raises:
        BusinessRuleError: optimistic-lock conflict OR insufficient on_hand
            (someone consumed the returned goods before cancel — manual
            intervention needed).
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
    expected_version = stock.version
    snapshot_avg_cost = stock.avg_cost

    result = await session.execute(
        update(Stock)
        .where(
            Stock.id == stock.id,
            Stock.version == expected_version,
            Stock.on_hand >= qty,
        )
        .values(
            on_hand=Stock.on_hand - qty,
            last_movement_at=now,
            version=Stock.version + 1,
        )
    )
    if result.rowcount == 0:
        raise BusinessRuleError(
            message=(
                f"Cannot reverse CN inbound for sku={sku_id} warehouse={warehouse_id}: "
                f"requested {qty} but stock was modified concurrently or on_hand "
                "is now below the returned quantity."
            ),
            error_code="STOCK_CONFLICT",
        )

    movement = StockMovement(
        organization_id=org_id,
        sku_id=sku_id,
        warehouse_id=warehouse_id,
        movement_type=StockMovementType.ADJUSTMENT_OUT,
        quantity=qty,
        unit_cost=snapshot_avg_cost,
        avg_cost_after=snapshot_avg_cost,  # WAC unchanged on reversal
        source_document_type=StockMovementSourceType.CN,
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
            movement_type=StockMovementType.ADJUSTMENT_OUT.value,
            quantity=qty,
            source_document_type=StockMovementSourceType.CN.value,
            source_document_id=source_document_id,
        ),
        session,
    )

    logger.info(
        "stock_sales_return_reversed",
        org_id=org_id,
        sku_id=sku_id,
        warehouse_id=warehouse_id,
        qty=str(qty),
        cn_id=source_document_id,
    )

    return stock


# ── Window 13: Stock Transfer + Stock Adjustment ─────────────────────────────


async def apply_transfer_ship_out(
    session: AsyncSession,
    *,
    org_id: int,
    sku_id: int,
    from_warehouse_id: int,
    to_warehouse_id: int,
    qty: Decimal,
    source_document_id: int,
    source_line_id: Optional[int] = None,
    batch_no: Optional[str] = None,
    expiry_date=None,
    actor_user_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> tuple[Stock, Stock, Decimal]:
    """Ship-out leg of a Stock Transfer (CONFIRMED → IN_TRANSIT).

    Atomic effects within the current transaction:
    1. From warehouse: on_hand -= qty (guarded so on_hand >= qty), version+=1.
       avg_cost is intentionally NOT recomputed — outbound moves do not affect
       weighted-average cost.
    2. To warehouse: in_transit += qty, version+=1. (Get-or-create row.)
    3. Insert one StockMovement row (TRANSFER_OUT, warehouse=From). The matching
       TRANSFER_IN row is written by ``apply_transfer_receive`` when goods land.
    4. Publish StockMovementOccurred event.

    Returns:
        Tuple ``(from_stock, to_stock, snapshot_avg_cost)`` — snapshot avg_cost
        is the From warehouse's avg_cost at ship time, which the service layer
        MUST persist into ``StockTransferLine.unit_cost_snapshot`` so the
        receive leg can recompute the destination weighted-average correctly.

    Raises:
        BusinessRuleError / InsufficientStockError — when From has too little
            on_hand or stocks were modified concurrently.
        ValueError — qty out of range.
    """
    if qty <= 0:
        raise ValueError("qty must be > 0")
    if from_warehouse_id == to_warehouse_id:
        raise ValueError("from_warehouse_id and to_warehouse_id must differ")

    # 1) Lock-and-load From stock row.
    stmt_from = select(Stock).where(
        Stock.sku_id == sku_id,
        Stock.warehouse_id == from_warehouse_id,
    )
    from_stock = (await session.execute(stmt_from)).scalar_one_or_none()
    if from_stock is None:
        raise InsufficientStockError(
            message=(
                f"No stock at from_warehouse={from_warehouse_id} for sku={sku_id}: "
                "cannot ship transfer."
            ),
            detail={"sku_id": sku_id, "warehouse_id": from_warehouse_id},
        )

    now = _utc_naive()
    expected_version = from_stock.version
    snapshot_avg_cost = from_stock.avg_cost

    # 2) Decrement From.on_hand atomically (guarded by version + capacity).
    result = await session.execute(
        update(Stock)
        .where(
            Stock.id == from_stock.id,
            Stock.version == expected_version,
            Stock.on_hand >= qty,
        )
        .values(
            on_hand=Stock.on_hand - qty,
            last_movement_at=now,
            version=Stock.version + 1,
        )
    )
    if result.rowcount == 0:
        raise InsufficientStockError(
            message=(
                f"Cannot ship {qty} of sku={sku_id} from warehouse={from_warehouse_id}: "
                f"on_hand={from_stock.on_hand} or row was modified concurrently."
            ),
            detail={
                "sku_id": sku_id,
                "warehouse_id": from_warehouse_id,
                "requested": str(qty),
            },
        )

    # 3) Increment To.in_transit (get-or-create destination row).
    to_stock = await _get_or_create_stock(
        session,
        org_id=org_id,
        sku_id=sku_id,
        warehouse_id=to_warehouse_id,
    )
    await session.execute(
        update(Stock)
        .where(Stock.id == to_stock.id)
        .values(
            in_transit=Stock.in_transit + qty,
            last_movement_at=now,
            version=Stock.version + 1,
        )
    )

    # 4) Audit movement (TRANSFER_OUT, warehouse=From).
    movement = StockMovement(
        organization_id=org_id,
        sku_id=sku_id,
        warehouse_id=from_warehouse_id,
        movement_type=StockMovementType.TRANSFER_OUT,
        quantity=qty,
        unit_cost=snapshot_avg_cost,  # for COGS-style traceability
        avg_cost_after=snapshot_avg_cost,  # WAC unchanged on outbound
        source_document_type=StockMovementSourceType.TRANSFER,
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
    await session.refresh(from_stock)
    await session.refresh(to_stock)

    await event_bus.publish(
        StockMovementOccurred(
            organization_id=org_id,
            sku_id=sku_id,
            warehouse_id=from_warehouse_id,
            movement_type=StockMovementType.TRANSFER_OUT.value,
            quantity=qty,
            source_document_type=StockMovementSourceType.TRANSFER.value,
            source_document_id=source_document_id,
        ),
        session,
    )

    logger.info(
        "stock_transfer_shipped",
        org_id=org_id,
        sku_id=sku_id,
        from_wh=from_warehouse_id,
        to_wh=to_warehouse_id,
        qty=str(qty),
        snapshot_avg_cost=str(snapshot_avg_cost),
        transfer_id=source_document_id,
    )

    return from_stock, to_stock, snapshot_avg_cost


async def apply_transfer_receive(
    session: AsyncSession,
    *,
    org_id: int,
    sku_id: int,
    to_warehouse_id: int,
    qty: Decimal,
    unit_cost_snapshot: Decimal,
    source_document_id: int,
    source_line_id: Optional[int] = None,
    batch_no: Optional[str] = None,
    expiry_date=None,
    actor_user_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> tuple[Stock, Decimal]:
    """Receive leg of a Stock Transfer (IN_TRANSIT → RECEIVED, possibly partial).

    Atomic effects:
    1. To warehouse: in_transit -= qty (guarded so in_transit >= qty),
       on_hand += qty, version+=1.
    2. Recompute weighted-average cost using the snapshot from ship time.
    3. Insert StockMovement (TRANSFER_IN).
    4. Publish StockMovementOccurred.

    Args:
        unit_cost_snapshot: From warehouse's avg_cost captured at ship time.
            This is the value that ``apply_transfer_ship_out`` returned and the
            service layer wrote into ``StockTransferLine.unit_cost_snapshot``.

    Returns:
        Tuple ``(stock, new_avg_cost)``.

    Raises:
        BusinessRuleError — concurrent modification or in_transit underflow.
        ValueError — qty / unit_cost out of range.
    """
    if qty <= 0:
        raise ValueError("qty must be > 0")
    if unit_cost_snapshot < 0:
        raise ValueError("unit_cost_snapshot must be >= 0")

    stmt = select(Stock).where(
        Stock.sku_id == sku_id,
        Stock.warehouse_id == to_warehouse_id,
    )
    stock = (await session.execute(stmt)).scalar_one_or_none()
    if stock is None:
        raise BusinessRuleError(
            message=(
                f"No stock row found at to_warehouse={to_warehouse_id} for sku={sku_id}: "
                "cannot receive transfer."
            ),
            error_code="STOCK_MISSING",
        )

    new_avg = compute_weighted_average(
        current_qty=stock.on_hand,
        current_avg_cost=stock.avg_cost,
        incoming_qty=qty,
        incoming_unit_cost=unit_cost_snapshot,
    )

    now = _utc_naive()
    expected_version = stock.version

    result = await session.execute(
        update(Stock)
        .where(
            Stock.id == stock.id,
            Stock.version == expected_version,
            Stock.in_transit >= qty,
        )
        .values(
            on_hand=Stock.on_hand + qty,
            in_transit=Stock.in_transit - qty,
            avg_cost=new_avg,
            last_cost=unit_cost_snapshot,
            last_movement_at=now,
            version=Stock.version + 1,
        )
    )
    if result.rowcount == 0:
        raise BusinessRuleError(
            message=(
                f"Cannot receive {qty} of sku={sku_id} at warehouse={to_warehouse_id}: "
                f"in_transit={stock.in_transit} or stock was modified concurrently."
            ),
            error_code="STOCK_CONFLICT",
        )

    movement = StockMovement(
        organization_id=org_id,
        sku_id=sku_id,
        warehouse_id=to_warehouse_id,
        movement_type=StockMovementType.TRANSFER_IN,
        quantity=qty,
        unit_cost=unit_cost_snapshot,
        avg_cost_after=new_avg,
        source_document_type=StockMovementSourceType.TRANSFER,
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
            warehouse_id=to_warehouse_id,
            movement_type=StockMovementType.TRANSFER_IN.value,
            quantity=qty,
            source_document_type=StockMovementSourceType.TRANSFER.value,
            source_document_id=source_document_id,
        ),
        session,
    )

    logger.info(
        "stock_transfer_received",
        org_id=org_id,
        sku_id=sku_id,
        to_wh=to_warehouse_id,
        qty=str(qty),
        unit_cost=str(unit_cost_snapshot),
        new_avg_cost=str(new_avg),
        transfer_id=source_document_id,
    )

    return stock, new_avg


async def apply_adjustment_increase(
    session: AsyncSession,
    *,
    org_id: int,
    sku_id: int,
    warehouse_id: int,
    qty: Decimal,
    unit_cost: Optional[Decimal],
    source_document_id: int,
    source_line_id: Optional[int] = None,
    batch_no: Optional[str] = None,
    expiry_date=None,
    actor_user_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> tuple[Stock, Decimal]:
    """Apply an inbound stock adjustment (盘盈 / inventory gain).

    Atomic effects:
    1. on_hand += qty, version+=1.
    2. avg_cost recomputed via weighted average. If ``unit_cost`` is None,
       inherit the current avg_cost (no WAC drift) — typical for "physical
       count discovered extra units of unknown origin".
    3. Insert StockMovement (ADJUSTMENT_IN).
    4. Publish StockMovementOccurred.

    Args:
        unit_cost: Optional per-unit cost for this gain. Defaults to current
            avg_cost when None (preserves WAC).
    """
    if qty <= 0:
        raise ValueError("qty must be > 0")
    if unit_cost is not None and unit_cost < 0:
        raise ValueError("unit_cost must be >= 0")

    stock = await _get_or_create_stock(
        session,
        org_id=org_id,
        sku_id=sku_id,
        warehouse_id=warehouse_id,
    )

    effective_unit_cost = unit_cost if unit_cost is not None else stock.avg_cost
    new_avg = compute_weighted_average(
        current_qty=stock.on_hand,
        current_avg_cost=stock.avg_cost,
        incoming_qty=qty,
        incoming_unit_cost=effective_unit_cost,
    )

    now = _utc_naive()
    expected_version = stock.version

    result = await session.execute(
        update(Stock)
        .where(Stock.id == stock.id, Stock.version == expected_version)
        .values(
            on_hand=Stock.on_hand + qty,
            avg_cost=new_avg,
            last_cost=effective_unit_cost,
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
        movement_type=StockMovementType.ADJUSTMENT_IN,
        quantity=qty,
        unit_cost=effective_unit_cost,
        avg_cost_after=new_avg,
        source_document_type=StockMovementSourceType.ADJUSTMENT,
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
            movement_type=StockMovementType.ADJUSTMENT_IN.value,
            quantity=qty,
            source_document_type=StockMovementSourceType.ADJUSTMENT.value,
            source_document_id=source_document_id,
        ),
        session,
    )

    logger.info(
        "stock_adjustment_increase_applied",
        org_id=org_id,
        sku_id=sku_id,
        warehouse_id=warehouse_id,
        qty=str(qty),
        unit_cost=str(effective_unit_cost),
        new_avg_cost=str(new_avg),
        adjustment_id=source_document_id,
    )

    return stock, new_avg


async def apply_adjustment_decrease(
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
    """Apply an outbound stock adjustment (盘亏 / inventory loss).

    Atomic effects:
    1. on_hand -= qty (guarded so on_hand >= qty), version+=1.
    2. avg_cost is intentionally NOT recomputed — outbound moves don't affect
       WAC. COGS = qty * avg_cost (snapshot for audit).
    3. Insert StockMovement (ADJUSTMENT_OUT, unit_cost=current avg_cost).
    4. Publish StockMovementOccurred.

    Raises:
        InsufficientStockError — on_hand < qty.
    """
    if qty <= 0:
        raise ValueError("qty must be > 0")

    stmt = select(Stock).where(
        Stock.sku_id == sku_id,
        Stock.warehouse_id == warehouse_id,
    )
    stock = (await session.execute(stmt)).scalar_one_or_none()
    if stock is None:
        raise InsufficientStockError(
            message=(
                f"No stock at warehouse={warehouse_id} for sku={sku_id}: "
                "cannot record loss."
            ),
            detail={"sku_id": sku_id, "warehouse_id": warehouse_id},
        )

    now = _utc_naive()
    expected_version = stock.version
    snapshot_avg_cost = stock.avg_cost

    result = await session.execute(
        update(Stock)
        .where(
            Stock.id == stock.id,
            Stock.version == expected_version,
            Stock.on_hand >= qty,
        )
        .values(
            on_hand=Stock.on_hand - qty,
            last_movement_at=now,
            version=Stock.version + 1,
        )
    )
    if result.rowcount == 0:
        raise InsufficientStockError(
            message=(
                f"Cannot decrease {qty} of sku={sku_id} at warehouse={warehouse_id}: "
                f"on_hand={stock.on_hand} or row was modified concurrently."
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
        movement_type=StockMovementType.ADJUSTMENT_OUT,
        quantity=qty,
        unit_cost=snapshot_avg_cost,
        avg_cost_after=snapshot_avg_cost,  # WAC unchanged on outbound
        source_document_type=StockMovementSourceType.ADJUSTMENT,
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
            movement_type=StockMovementType.ADJUSTMENT_OUT.value,
            quantity=qty,
            source_document_type=StockMovementSourceType.ADJUSTMENT.value,
            source_document_id=source_document_id,
        ),
        session,
    )

    logger.info(
        "stock_adjustment_decrease_applied",
        org_id=org_id,
        sku_id=sku_id,
        warehouse_id=warehouse_id,
        qty=str(qty),
        snapshot_avg_cost=str(snapshot_avg_cost),
        adjustment_id=source_document_id,
    )

    return stock, snapshot_avg_cost
