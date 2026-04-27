#!/usr/bin/env python3
"""
Seed script: create initial stock records (200 SKUs × 3 warehouses = 600 Stock rows)
plus matching StockMovement audit records (ADJUSTMENT_IN / OPENING).

Stock quantities by warehouse:
  WH-KL  (Main)    : 1.5× base quantity
  WH-PG  (Penang)  : 1.0× base quantity ± 20%
  WH-JB  (JB)      : 1.0× base quantity ± 20%

avg_cost = unit_price_excl_tax × 0.65 (approx. 35% gross margin)

Run inside the container:
  docker compose exec backend python scripts/seed_initial_stock.py

Idempotent: safe to re-run; existing Stock rows (sku_id, warehouse_id) are skipped.
"""

from __future__ import annotations

import asyncio
import os
import sys
import random
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.enums import StockMovementType, StockMovementSourceType
from app.models.sku import SKU
from app.models.organization import Warehouse
from app.models.stock import Stock, StockMovement

log = structlog.get_logger()

# Category prefix → base_qty (on_hand)
# These represent realistic stocking levels for a Malaysian distributor
CATEGORY_BASE_QTY: dict[str, int] = {
    "BEV":  400,   # Beverages: fast-moving, high volume
    "INF":  300,   # Instant food: very fast-moving
    "SNK":  250,   # Snacks: medium-fast
    "DAI":  200,   # Dairy: moderate (shorter shelf life)
    "CKG":  150,   # Cooking essentials: stable demand
    "RCO":  80,    # Rice/oil/flour: bulky, fewer units
    "ORL":  120,   # Oral care
    "HAI":  100,   # Hair care
    "SKN":  80,    # Skin care
    "CLN":  120,   # Cleaning: medium volume
    "OTC":  80,    # OTC medication: moderated quantity
    "APL":  30,    # Small appliances: low volume
    "STA":  100,   # Stationery
}

FOUR = Decimal("0.0001")
COST_RATIO = Decimal("0.65")  # avg_cost = 65% of excl. price


def _get_prefix(sku_code: str) -> str:
    """Extract category prefix from SKU code like SKU-BEV-0001."""
    parts = sku_code.split("-")
    return parts[1] if len(parts) >= 2 else "BEV"


def _base_qty(sku_code: str) -> Decimal:
    prefix = _get_prefix(sku_code)
    return Decimal(str(CATEGORY_BASE_QTY.get(prefix, 100)))


def _kl_qty(base: Decimal) -> Decimal:
    return (base * Decimal("1.5")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _branch_qty(base: Decimal) -> Decimal:
    # ±20% random variance
    factor = Decimal(str(round(random.uniform(0.80, 1.20), 2)))
    return (base * factor).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _avg_cost(unit_price_excl_tax: Decimal) -> Decimal:
    return (unit_price_excl_tax * COST_RATIO).quantize(FOUR, rounding=ROUND_HALF_UP)


async def seed_initial_stock(session: AsyncSession) -> tuple[int, int]:
    """Returns (stock_created, movement_created)."""
    random.seed(42)  # deterministic for idempotency

    # Load all active SKUs for org 1
    sku_result = await session.execute(
        select(SKU).where(
            SKU.organization_id == 1,
            SKU.deleted_at.is_(None),
            SKU.is_active.is_(True),
        )
    )
    skus = sku_result.scalars().all()
    log.info("skus_loaded", count=len(skus))

    # Load all warehouses for org 1
    wh_result = await session.execute(
        select(Warehouse).where(
            Warehouse.organization_id == 1,
            Warehouse.is_active.is_(True),
        )
    )
    warehouses = wh_result.scalars().all()
    log.info("warehouses_loaded", count=len(warehouses), codes=[w.code for w in warehouses])

    if not skus:
        log.warning("no_skus_found", hint="Run seed_skus.py first")
        return 0, 0

    if not warehouses:
        log.warning("no_warehouses_found", hint="Run seed_master_data.py first")
        return 0, 0

    # Identify KL main warehouse
    kl_wh = next((w for w in warehouses if "KL" in w.code), warehouses[0])
    branch_whs = [w for w in warehouses if w.id != kl_wh.id]

    # Load existing (sku_id, warehouse_id) pairs
    existing_result = await session.execute(
        select(Stock.sku_id, Stock.warehouse_id)
    )
    existing_pairs = {(row[0], row[1]) for row in existing_result.all()}
    log.info("existing_stock_rows", count=len(existing_pairs))

    now = datetime.utcnow()
    stock_created = 0
    movement_created = 0

    for sku in skus:
        base = _base_qty(sku.code)
        excl_price = sku.unit_price_excl_tax or Decimal("10.00")
        cost = _avg_cost(excl_price)

        wh_qtys: list[tuple[Warehouse, Decimal]] = []

        # KL main warehouse
        kl_qty = _kl_qty(base)
        wh_qtys.append((kl_wh, kl_qty))

        # Branch warehouses
        for wh in branch_whs:
            wh_qtys.append((wh, _branch_qty(base)))

        for warehouse, on_hand_qty in wh_qtys:
            if (sku.id, warehouse.id) in existing_pairs:
                log.debug("stock_exists", sku=sku.code, wh=warehouse.code)
                continue

            # Create Stock row
            stock = Stock(
                organization_id=1,
                sku_id=sku.id,
                warehouse_id=warehouse.id,
                on_hand=on_hand_qty,
                reserved=Decimal("0"),
                quality_hold=Decimal("0"),
                incoming=Decimal("0"),
                in_transit=Decimal("0"),
                avg_cost=cost,
                last_cost=cost,
                initial_on_hand=on_hand_qty,
                initial_avg_cost=cost,
                last_movement_at=now,
            )
            session.add(stock)
            stock_created += 1

            # Create paired StockMovement (audit trail)
            movement = StockMovement(
                organization_id=1,
                sku_id=sku.id,
                warehouse_id=warehouse.id,
                movement_type=StockMovementType.ADJUSTMENT_IN,
                quantity=on_hand_qty,
                unit_cost=cost,
                avg_cost_after=cost,
                source_document_type=StockMovementSourceType.OPENING,
                source_document_id=0,
                notes="Initial stock on system launch",
                occurred_at=now,
            )
            session.add(movement)
            movement_created += 1

        # Flush every 50 SKUs to avoid very large transactions
        if stock_created % 150 == 0 and stock_created > 0:
            await session.flush()
            log.info("progress", stock_created=stock_created, movement_created=movement_created)

    await session.flush()
    log.info(
        "initial_stock_seeded",
        stock_created=stock_created,
        movement_created=movement_created,
        skus=len(skus),
        warehouses=len(warehouses),
    )
    return stock_created, movement_created


async def main() -> None:
    import logging

    logging.basicConfig(level=logging.INFO)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as session:
        async with session.begin():
            stock_n, move_n = await seed_initial_stock(session)

    await engine.dispose()
    print(f"\n✅ Seed complete — {stock_n} Stock rows + {move_n} StockMovement rows created.")


if __name__ == "__main__":
    asyncio.run(main())
