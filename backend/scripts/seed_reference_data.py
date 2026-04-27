#!/usr/bin/env python3
"""
Seed script: create reference / master data needed for SKU creation and business flow.

Creates (idempotently):
  1. Currencies  — MYR (base), USD, SGD, CNY
  2. TaxRates    — SST 10% / 6% / 0% (org_id=1)
  3. UOMs        — PCS, KG, LITRE, BOX, CTN, DOZEN, METER, SET (org_id=1)
  4. Brands      — 5 demo brands (org_id=1)
  5. Categories  — 3 top-level + 9 sub-categories (org_id=1)

Requires org_id=1 to already exist (run seed_master_data.py first).

Run inside the container:
  docker compose exec backend python scripts/seed_reference_data.py
"""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.enums import TaxType
from app.models.master import Brand, Category, Currency, TaxRate, UOM

log = structlog.get_logger()

ORG_ID = 1


# ── 1. Currencies ─────────────────────────────────────────────────────────────

CURRENCIES = [
    {"code": "MYR", "name": "Malaysian Ringgit",   "symbol": "RM",  "decimal_places": 2},
    {"code": "USD", "name": "US Dollar",            "symbol": "$",   "decimal_places": 2},
    {"code": "SGD", "name": "Singapore Dollar",     "symbol": "S$",  "decimal_places": 2},
    {"code": "CNY", "name": "Chinese Yuan Renminbi","symbol": "¥",   "decimal_places": 2},
    {"code": "EUR", "name": "Euro",                 "symbol": "€",   "decimal_places": 2},
]


async def _seed_currencies(session: AsyncSession) -> None:
    for c in CURRENCIES:
        result = await session.execute(
            select(Currency).where(Currency.code == c["code"])
        )
        if result.scalar_one_or_none() is not None:
            log.info("currency_exists", code=c["code"])
            continue
        session.add(Currency(**c))
        log.info("currency_created", code=c["code"])
    await session.flush()


# ── 2. TaxRates ───────────────────────────────────────────────────────────────

TAX_RATES = [
    {
        "code": "SST-10",
        "name": "SST 10% (Sales Tax)",
        "rate": "10.00",
        "tax_type": TaxType.SALES_TAX,
        "is_default": False,
    },
    {
        "code": "SST-6",
        "name": "SST 6% (Service Tax)",
        "rate": "6.00",
        "tax_type": TaxType.SERVICE_TAX,
        "is_default": False,
    },
    {
        "code": "SST-0",
        "name": "SST 0% (Exempt)",
        "rate": "0.00",
        "tax_type": TaxType.EXEMPT,
        "is_default": True,
    },
]


async def _seed_tax_rates(session: AsyncSession) -> None:
    for tr in TAX_RATES:
        result = await session.execute(
            select(TaxRate).where(
                TaxRate.organization_id == ORG_ID,
                TaxRate.code == tr["code"],
            )
        )
        if result.scalar_one_or_none() is not None:
            log.info("tax_rate_exists", code=tr["code"])
            continue
        session.add(TaxRate(organization_id=ORG_ID, **tr))
        log.info("tax_rate_created", code=tr["code"])
    await session.flush()


# ── 3. UOMs ───────────────────────────────────────────────────────────────────

UOMS = [
    {"code": "PCS",    "name": "Piece",      "name_zh": "个"},
    {"code": "KG",     "name": "Kilogram",   "name_zh": "千克"},
    {"code": "G",      "name": "Gram",       "name_zh": "克"},
    {"code": "LITRE",  "name": "Litre",      "name_zh": "升"},
    {"code": "ML",     "name": "Millilitre", "name_zh": "毫升"},
    {"code": "BOX",    "name": "Box",        "name_zh": "箱"},
    {"code": "CTN",    "name": "Carton",     "name_zh": "纸箱"},
    {"code": "DOZEN",  "name": "Dozen",      "name_zh": "打"},
    {"code": "METER",  "name": "Meter",      "name_zh": "米"},
    {"code": "SET",    "name": "Set",        "name_zh": "套"},
    {"code": "ROLL",   "name": "Roll",       "name_zh": "卷"},
    {"code": "PAX",    "name": "Pax",        "name_zh": "人次"},
]


async def _seed_uoms(session: AsyncSession) -> None:
    for u in UOMS:
        result = await session.execute(
            select(UOM).where(
                UOM.organization_id == ORG_ID,
                UOM.code == u["code"],
            )
        )
        if result.scalar_one_or_none() is not None:
            log.info("uom_exists", code=u["code"])
            continue
        session.add(UOM(organization_id=ORG_ID, **u))
        log.info("uom_created", code=u["code"])
    await session.flush()


# ── 4. Brands ─────────────────────────────────────────────────────────────────

BRANDS = [
    {"code": "GENERIC",  "name": "Generic / Unbranded"},
    {"code": "NESTLEMY",  "name": "Nestlé Malaysia"},
    {"code": "DELI",     "name": "Deli Office Supplies"},
    {"code": "PANASON",  "name": "Panasonic"},
    {"code": "LOCALMY",  "name": "Local Malaysia Brand"},
]


async def _seed_brands(session: AsyncSession) -> None:
    for b in BRANDS:
        result = await session.execute(
            select(Brand).where(
                Brand.organization_id == ORG_ID,
                Brand.code == b["code"],
                Brand.deleted_at.is_(None),
            )
        )
        if result.scalar_one_or_none() is not None:
            log.info("brand_exists", code=b["code"])
            continue
        session.add(Brand(organization_id=ORG_ID, **b))
        log.info("brand_created", code=b["code"])
    await session.flush()


# ── 5. Categories ─────────────────────────────────────────────────────────────
# Format: (code, name, name_zh, parent_code | None)

CATEGORIES: list[tuple[str, str, str, str | None]] = [
    # Top level
    ("FOOD",    "Food & Beverages",    "食品饮料",   None),
    ("OFFICE",  "Office Supplies",     "办公用品",   None),
    ("ELEC",    "Electronics",         "电子产品",   None),
    # Food sub-categories
    ("BEVER",   "Beverages",           "饮料",       "FOOD"),
    ("SNACK",   "Snacks & Confectionery", "零食糖果", "FOOD"),
    ("DAIRY",   "Dairy & Eggs",        "乳制品鸡蛋", "FOOD"),
    # Office sub-categories
    ("PAPER",   "Paper & Printing",    "纸张打印",   "OFFICE"),
    ("STATIO",  "Stationery",          "文具",       "OFFICE"),
    # Electronics sub-categories
    ("LAPTOP",  "Laptops & Computers", "电脑笔记本", "ELEC"),
    ("PHONE",   "Mobile Phones",       "手机",       "ELEC"),
    ("PERIPH",  "Peripherals",         "外设配件",   "ELEC"),
]


async def _seed_categories(session: AsyncSession) -> None:
    # Build code → id map as we insert
    code_to_id: dict[str, int] = {}

    # Load existing
    result = await session.execute(
        select(Category).where(
            Category.organization_id == ORG_ID,
            Category.deleted_at.is_(None),
        )
    )
    for cat in result.scalars().all():
        code_to_id[cat.code] = cat.id

    for code, name, name_zh, parent_code in CATEGORIES:
        if code in code_to_id:
            log.info("category_exists", code=code)
            continue

        parent_id = code_to_id.get(parent_code) if parent_code else None

        # Build path
        if parent_code and parent_code in code_to_id:
            # Find parent path
            parent_result = await session.execute(
                select(Category).where(Category.id == code_to_id[parent_code])
            )
            parent_cat = parent_result.scalar_one_or_none()
            parent_path = parent_cat.path if parent_cat and parent_cat.path else parent_code
            path = f"{parent_path}/{code}"
        else:
            path = code

        cat = Category(
            organization_id=ORG_ID,
            code=code,
            name=name,
            name_zh=name_zh,
            parent_id=parent_id,
            path=path,
        )
        session.add(cat)
        await session.flush()
        code_to_id[code] = cat.id
        log.info("category_created", code=code, path=path)


# ── Entry point ───────────────────────────────────────────────────────────────

async def main() -> None:
    import logging
    logging.basicConfig(level=logging.INFO)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as session:
        async with session.begin():
            await _seed_currencies(session)
            await _seed_tax_rates(session)
            await _seed_uoms(session)
            await _seed_brands(session)
            await _seed_categories(session)

    await engine.dispose()
    log.info("seed_reference_complete")
    print("\n✅ Reference data seeded:")
    print(f"   Currencies : {len(CURRENCIES)}")
    print(f"   Tax Rates  : {len(TAX_RATES)}")
    print(f"   UOMs       : {len(UOMS)}")
    print(f"   Brands     : {len(BRANDS)}")
    print(f"   Categories : {len(CATEGORIES)}")


if __name__ == "__main__":
    asyncio.run(main())
