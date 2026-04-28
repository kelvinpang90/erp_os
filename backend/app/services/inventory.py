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

from app.core.exceptions import BusinessRuleError
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


# ── Reserved for future windows ──────────────────────────────────────────────


async def apply_sales_out(*args, **kwargs):  # pragma: no cover — W10
    """Reserved for Window 10 (Sales Order delivery)."""
    raise NotImplementedError("apply_sales_out is implemented in Window 10.")


async def apply_transfer_out(*args, **kwargs):  # pragma: no cover — W13
    """Reserved for Window 13 (Stock Transfer)."""
    raise NotImplementedError("apply_transfer_out is implemented in Window 13.")


async def apply_transfer_in(*args, **kwargs):  # pragma: no cover — W13
    """Reserved for Window 13 (Stock Transfer)."""
    raise NotImplementedError("apply_transfer_in is implemented in Window 13.")


async def apply_adjustment(*args, **kwargs):  # pragma: no cover — W13
    """Reserved for Window 13 (Stock Adjustment)."""
    raise NotImplementedError("apply_adjustment is implemented in Window 13.")
