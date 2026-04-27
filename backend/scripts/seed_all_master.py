#!/usr/bin/env python3
"""
Master seed orchestrator — run all seed scripts in dependency order.

Order:
  1. seed_master_data      → org, roles, users, warehouses
  2. seed_reference_data   → currencies, tax rates, UOMs, brands, categories, MSIC codes
  3. seed_skus             → 200 Malaysian SKUs
  4. seed_suppliers        → 30 suppliers
  5. seed_customers        → 50 customers
  6. seed_initial_stock    → 600 Stock rows + StockMovement audit

Run inside the container:
  docker compose exec backend python scripts/seed_all_master.py

Each step is idempotent; re-running is safe.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

log = structlog.get_logger()


def _separator(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


async def run_all() -> None:
    import logging

    logging.basicConfig(level=logging.WARNING)  # suppress noisy SQLAlchemy INFO

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    total_start = time.perf_counter()

    # ── Step 1: Master data ──────────────────────────────────────────────────
    _separator("Step 1/6  seed_master_data  (org / roles / users / warehouses)")
    from scripts.seed_master_data import (
        _get_or_create_org,
        _seed_permissions,
        _seed_roles,
        _seed_users,
        _seed_warehouses,
    )

    async with SessionLocal() as session:
        async with session.begin():
            org = await _get_or_create_org(session)
            perm_map = await _seed_permissions(session)
            role_map = await _seed_roles(session, org, perm_map)
            await _seed_users(session, org, role_map)
            await _seed_warehouses(session, org)
    print("  ✓ Done")

    # ── Step 2: Reference data ───────────────────────────────────────────────
    _separator("Step 2/6  seed_reference_data  (currencies / tax / UOM / brands / categories / MSIC)")
    from scripts.seed_reference_data import (
        _seed_currencies,
        _seed_tax_rates,
        _seed_uoms,
        _seed_brands,
        _seed_categories,
        _seed_msic_codes,
    )

    async with SessionLocal() as session:
        async with session.begin():
            await _seed_currencies(session)
            await _seed_tax_rates(session)
            await _seed_uoms(session)
            await _seed_brands(session)
            await _seed_categories(session)
            await _seed_msic_codes(session)
    print("  ✓ Done")

    # ── Step 3: SKUs ─────────────────────────────────────────────────────────
    _separator("Step 3/6  seed_skus  (200 Malaysian SKUs)")
    from scripts.seed_skus import seed_skus

    async with SessionLocal() as session:
        async with session.begin():
            created = await seed_skus(session)
    print(f"  ✓ Done — {created} SKUs created")

    # ── Step 4: Suppliers ────────────────────────────────────────────────────
    _separator("Step 4/6  seed_suppliers  (30 suppliers)")
    from scripts.seed_suppliers import seed_suppliers

    async with SessionLocal() as session:
        async with session.begin():
            created = await seed_suppliers(session)
    print(f"  ✓ Done — {created} suppliers created")

    # ── Step 5: Customers ────────────────────────────────────────────────────
    _separator("Step 5/6  seed_customers  (50 customers: 30 B2B + 20 B2C)")
    from scripts.seed_customers import seed_customers

    async with SessionLocal() as session:
        async with session.begin():
            created = await seed_customers(session)
    print(f"  ✓ Done — {created} customers created")

    # ── Step 6: Initial stock ────────────────────────────────────────────────
    _separator("Step 6/6  seed_initial_stock  (600 Stock rows)")
    from scripts.seed_initial_stock import seed_initial_stock

    async with SessionLocal() as session:
        async with session.begin():
            stock_n, move_n = await seed_initial_stock(session)
    print(f"  ✓ Done — {stock_n} Stock rows + {move_n} StockMovement rows created")

    # ── Summary ──────────────────────────────────────────────────────────────
    elapsed = time.perf_counter() - total_start
    await engine.dispose()

    print(f"\n{'═' * 60}")
    print(f"  ✅  All master data seeded in {elapsed:.1f}s")
    print(f"{'═' * 60}\n")
    print("Verification query:")
    print("""  docker compose exec mysql mysql -u root -p erp_os -e "
    SELECT 'skus'      AS entity, COUNT(*) AS count FROM skus       WHERE organization_id=1 AND deleted_at IS NULL
    UNION SELECT 'suppliers',     COUNT(*)           FROM suppliers  WHERE organization_id=1 AND deleted_at IS NULL
    UNION SELECT 'customers',     COUNT(*)           FROM customers  WHERE organization_id=1 AND deleted_at IS NULL
    UNION SELECT 'stocks',        COUNT(*)           FROM stocks     WHERE organization_id=1
    UNION SELECT 'brands',        COUNT(*)           FROM brands     WHERE organization_id=1 AND deleted_at IS NULL
    UNION SELECT 'msic_codes',    COUNT(*)           FROM msic_codes;
  " """)


if __name__ == "__main__":
    asyncio.run(run_all())
