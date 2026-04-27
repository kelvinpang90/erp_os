#!/usr/bin/env python3
"""
Seed script: create reference / master data needed for SKU creation and business flow.

Creates (idempotently):
  1. Currencies  — MYR (base), USD, SGD, CNY, EUR
  2. TaxRates    — SST 10% / 6% / 0% (org_id=1)
  3. UOMs        — 12 types (org_id=1)
  4. MSICCodes   — 20 common Malaysian industry codes (global, no org)
  5. Brands      — ~65 Malaysian brands (org_id=1)
  6. Categories  — 7 top-level + 20 sub-categories (org_id=1)

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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.enums import TaxType
from app.models.master import Brand, Category, Currency, MSICCode, TaxRate, UOM

log = structlog.get_logger()

ORG_ID = 1


# ── 1. Currencies ─────────────────────────────────────────────────────────────

CURRENCIES = [
    {"code": "MYR", "name": "Malaysian Ringgit",    "symbol": "RM",  "decimal_places": 2},
    {"code": "USD", "name": "US Dollar",             "symbol": "$",   "decimal_places": 2},
    {"code": "SGD", "name": "Singapore Dollar",      "symbol": "S$",  "decimal_places": 2},
    {"code": "CNY", "name": "Chinese Yuan Renminbi", "symbol": "¥",   "decimal_places": 2},
    {"code": "EUR", "name": "Euro",                  "symbol": "€",   "decimal_places": 2},
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


# ── 4. MSIC Codes ─────────────────────────────────────────────────────────────
# Global lookup table (no organization_id). Covers all suppliers in this demo.

MSIC_CODES = [
    # Retail
    {"code": "47110", "name": "Supermarkets and Hypermarkets",                          "category": "Retail"},
    {"code": "47210", "name": "Retail sale of food in specialised stores",              "category": "Retail"},
    {"code": "47411", "name": "Retail sale of computers, peripherals and software",     "category": "Retail"},
    {"code": "47591", "name": "Retail sale of electrical household appliances",         "category": "Retail"},
    {"code": "47711", "name": "Retail sale of clothing in specialised stores",         "category": "Retail"},
    {"code": "47730", "name": "Dispensing chemist in specialised stores",               "category": "Retail"},
    {"code": "47810", "name": "Retail sale via food stalls and markets",               "category": "Retail"},
    {"code": "47990", "name": "Other retail sale not in stores, stalls or markets",    "category": "Retail"},
    # Wholesale
    {"code": "46110", "name": "Agents in sale of agricultural raw materials",           "category": "Wholesale"},
    {"code": "46310", "name": "Wholesale of food, beverages and tobacco",               "category": "Wholesale"},
    {"code": "46410", "name": "Wholesale of textiles, clothing and footwear",           "category": "Wholesale"},
    {"code": "46610", "name": "Wholesale of solid, liquid and gaseous fuels",           "category": "Wholesale"},
    {"code": "46690", "name": "Wholesale of other machinery, equipment and supplies",   "category": "Wholesale"},
    {"code": "46900", "name": "Non-specialised wholesale trade",                        "category": "Wholesale"},
    # Manufacturing
    {"code": "10110", "name": "Processing and preserving of meat",                      "category": "Manufacturing"},
    {"code": "10710", "name": "Manufacture of bread, fresh pastry goods and cakes",    "category": "Manufacturing"},
    {"code": "10720", "name": "Manufacture of rusks and biscuits",                     "category": "Manufacturing"},
    {"code": "10810", "name": "Manufacture of sugar",                                   "category": "Manufacturing"},
    # Services
    {"code": "46510", "name": "Wholesale of computers, peripherals and software",       "category": "Wholesale"},
    {"code": "73100", "name": "Advertising activities",                                  "category": "Services"},
]


async def _seed_msic_codes(session: AsyncSession) -> None:
    for m in MSIC_CODES:
        result = await session.execute(
            select(MSICCode).where(MSICCode.code == m["code"])
        )
        if result.scalar_one_or_none() is not None:
            log.info("msic_exists", code=m["code"])
            continue
        session.add(MSICCode(**m))
        log.info("msic_created", code=m["code"])
    await session.flush()


# ── 5. Brands ─────────────────────────────────────────────────────────────────
# ~65 authentic Malaysian brands across all product categories.

BRANDS = [
    # ── Previously seeded (kept for idempotency) ──────────────────────────────
    {"code": "GENERIC",     "name": "Generic / Unbranded"},
    {"code": "NESTLEMY",    "name": "Nestlé Malaysia"},
    {"code": "DELI",        "name": "Deli Office Supplies"},
    {"code": "PANASON",     "name": "Panasonic"},
    {"code": "LOCALMY",     "name": "Local Malaysia Brand"},
    # ── Hot beverages ─────────────────────────────────────────────────────────
    {"code": "MILO",        "name": "Milo"},
    {"code": "NESCAFE",     "name": "Nescafé"},
    {"code": "AIKCHEONG",   "name": "Aik Cheong"},
    {"code": "OLDTOWN",     "name": "Old Town White Coffee"},
    {"code": "BOHTEA",      "name": "Boh Tea"},
    {"code": "LIPTON",      "name": "Lipton"},
    # ── Cold beverages ────────────────────────────────────────────────────────
    {"code": "COCACOLA",    "name": "Coca-Cola"},
    {"code": "ONEPLUS",     "name": "100Plus"},
    {"code": "YEOS",        "name": "Yeo's"},
    {"code": "SPRITZER",    "name": "Spritzer"},
    {"code": "VITAGEN",     "name": "Vitagen"},
    {"code": "DUTCHLADY",   "name": "Dutch Lady"},
    # ── Instant food ──────────────────────────────────────────────────────────
    {"code": "MAGGI",       "name": "Maggi"},
    {"code": "MAMEE",       "name": "Mamee"},
    {"code": "CINTAN",      "name": "Cintan"},
    {"code": "MYKUALI",     "name": "MyKuali"},
    {"code": "INDOMIE",     "name": "Indomie"},
    # ── Snacks & confectionery ────────────────────────────────────────────────
    {"code": "MAMEED",      "name": "Mamee Double Decker"},
    {"code": "JACKNJILL",   "name": "Jack 'n Jill"},
    {"code": "TWISTIES",    "name": "Twisties"},
    {"code": "OREO",        "name": "Oreo"},
    {"code": "HIGH5",       "name": "High-5"},
    {"code": "GARDENIA",    "name": "Gardenia"},
    {"code": "JULIES",      "name": "Julie's"},
    # ── Dairy ─────────────────────────────────────────────────────────────────
    {"code": "FARMFRESH",   "name": "Farm Fresh"},
    {"code": "FRNMAGNOLIA", "name": "F&N Magnolia"},
    {"code": "MARIGOLD",    "name": "Marigold"},
    # ── Cooking essentials ────────────────────────────────────────────────────
    {"code": "KNORR",       "name": "Knorr"},
    {"code": "AJINOMOTO",   "name": "Ajinomoto"},
    {"code": "ALAGAPPAS",   "name": "Alagappa's"},
    {"code": "BABAS",       "name": "Baba's"},
    {"code": "ADABI",       "name": "Adabi"},
    {"code": "KIKKOMAN",    "name": "Kikkoman"},
    # ── Rice, oil & flour ─────────────────────────────────────────────────────
    {"code": "JASMINE",     "name": "Jasmine Rice"},
    {"code": "FAIZA",       "name": "Faiza"},
    {"code": "SEAHORSE",    "name": "Sea Horse Cooking Oil"},
    {"code": "BLUEKEY",     "name": "Blue Key Flour"},
    # ── Personal care ─────────────────────────────────────────────────────────
    {"code": "DARLIE",      "name": "Darlie"},
    {"code": "COLGATE",     "name": "Colgate"},
    {"code": "SENSODYNE",   "name": "Sensodyne"},
    {"code": "DETTOL",      "name": "Dettol"},
    {"code": "LIFEBUOY",    "name": "Lifebuoy"},
    {"code": "JOHNSONS",    "name": "Johnson's Baby"},
    {"code": "PANTENE",     "name": "Pantene"},
    {"code": "HEADSHLD",    "name": "Head & Shoulders"},
    # ── Household cleaning ────────────────────────────────────────────────────
    {"code": "DYNAMO",      "name": "Dynamo"},
    {"code": "BREEZE",      "name": "Breeze"},
    {"code": "TOPCLEAN",    "name": "Top"},
    {"code": "GLADE",       "name": "Glade"},
    {"code": "HARPIC",      "name": "Harpic"},
    # ── Pharmacy / OTC ────────────────────────────────────────────────────────
    {"code": "PANADOL",     "name": "Panadol"},
    {"code": "STREPSILS",   "name": "Strepsils"},
    {"code": "VICKS",       "name": "Vicks"},
    {"code": "TIGERBALM",   "name": "Tiger Balm"},
    {"code": "COUNTERPAIN", "name": "Counterpain"},
    {"code": "EAGLEBRAND",  "name": "Eagle Brand"},
    # ── Small electronics ─────────────────────────────────────────────────────
    {"code": "SHARP",       "name": "Sharp"},
    {"code": "PENSONIC",    "name": "Pensonic"},
    {"code": "KHIND",       "name": "Khind"},
    {"code": "MILUX",       "name": "Milux"},
    # ── Stationery ────────────────────────────────────────────────────────────
    {"code": "CAMPAP",      "name": "Campap"},
    {"code": "FABERCAS",    "name": "Faber-Castell"},
    {"code": "STABILO",     "name": "Stabilo"},
    {"code": "UHU",         "name": "UHU"},
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


# ── 6. Categories ─────────────────────────────────────────────────────────────
# Format: (code, name, name_zh, parent_code | None)
# Existing 3 top-level + 9 sub kept; new top-levels and sub-categories added.

CATEGORIES: list[tuple[str, str, str, str | None]] = [
    # ── Existing top-level ────────────────────────────────────────────────────
    ("FOOD",        "Food & Beverages",       "食品饮料",    None),
    ("OFFICE",      "Office Supplies",        "办公用品",    None),
    ("ELEC",        "Electronics",            "电子产品",    None),
    # ── Existing FOOD sub-categories ──────────────────────────────────────────
    ("BEVER",       "Beverages",              "饮料",        "FOOD"),
    ("SNACK",       "Snacks & Confectionery", "零食糖果",    "FOOD"),
    ("DAIRY",       "Dairy & Eggs",           "乳制品鸡蛋",  "FOOD"),
    # ── Existing OFFICE sub-categories ───────────────────────────────────────
    ("PAPER",       "Paper & Printing",       "纸张打印",    "OFFICE"),
    ("STATIO",      "Stationery",             "文具",        "OFFICE"),
    # ── Existing ELEC sub-categories ─────────────────────────────────────────
    ("LAPTOP",      "Laptops & Computers",    "电脑笔记本",  "ELEC"),
    ("PHONE",       "Mobile Phones",          "手机",        "ELEC"),
    ("PERIPH",      "Peripherals",            "外设配件",    "ELEC"),
    # ── New FOOD sub-categories ───────────────────────────────────────────────
    ("INSTANT_FOOD","Instant Food",           "即食品",      "FOOD"),
    ("COOKING_ESS", "Cooking Essentials",     "调味料",      "FOOD"),
    ("RICE_OIL",    "Rice, Oil & Flour",      "主粮油面",    "FOOD"),
    # ── New top-level: Personal Care ──────────────────────────────────────────
    ("PERSONAL_CARE","Personal Care",         "个人护理",    None),
    ("ORAL_CARE",   "Oral Care",              "口腔护理",    "PERSONAL_CARE"),
    ("HAIR_CARE",   "Hair Care",              "护发",        "PERSONAL_CARE"),
    ("SKIN_CARE",   "Skin Care",              "护肤",        "PERSONAL_CARE"),
    ("CLEANING",    "Household Cleaning",     "家居清洁",    "PERSONAL_CARE"),
    # ── New top-level: Pharmacy ───────────────────────────────────────────────
    ("PHARMACY",    "Pharmacy & Health",      "药品健康",    None),
    ("OTC_MED",     "OTC Medication",         "非处方药",    "PHARMACY"),
    ("HEALTH_SUP",  "Health Supplements",     "保健品",      "PHARMACY"),
    # ── New ELEC sub-category: small appliances ───────────────────────────────
    ("SMALL_APPL",  "Small Appliances",       "小家电",      "ELEC"),
]


async def _seed_categories(session: AsyncSession) -> None:
    code_to_id: dict[str, int] = {}

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

        if parent_code and parent_code in code_to_id:
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
            await _seed_msic_codes(session)
            await _seed_brands(session)
            await _seed_categories(session)

    await engine.dispose()
    log.info("seed_reference_complete")
    print("\n✅ Reference data seeded:")
    print(f"   Currencies : {len(CURRENCIES)}")
    print(f"   Tax Rates  : {len(TAX_RATES)}")
    print(f"   UOMs       : {len(UOMS)}")
    print(f"   MSIC Codes : {len(MSIC_CODES)}")
    print(f"   Brands     : {len(BRANDS)}")
    print(f"   Categories : {len(CATEGORIES)}")


if __name__ == "__main__":
    asyncio.run(main())
