#!/usr/bin/env python3
"""Seed ~500 transactional documents (PO + SO + Invoice) over the past 6
months so the dashboard, reports, and AI summary have data to chart on.

Distribution (rough — randomised within bounds):
  ~150 Purchase Orders     (status: 60% FULLY_RECEIVED, 25% PARTIAL_RECEIVED, 15% CONFIRMED)
  ~250 Sales Orders        (status: 50% INVOICED, 30% FULLY_SHIPPED, 15% CONFIRMED, 5% DRAFT)
  ~150 Invoices            (status: 60% FINAL, 25% VALIDATED, 10% SUBMITTED, 5% DRAFT)

Seasonal weighting:
  - Ramadan (Mar–Apr 2026)   ×1.4
  - CNY (Feb 2026)           ×1.3
  - Year-end (Dec 2025)      ×1.5

This intentionally bypasses the service-layer state machine and writes rows
directly. The destination tables are TRUNCATEd by demo_reset before this
runs, so referential integrity is the only contract we have to honour.

Usage (standalone):
  docker compose exec backend python scripts/seed_transactional.py

Idempotent: appends — re-running grows the dataset. demo_reset wipes first,
so in normal flow you don't need to worry about duplication.
"""

from __future__ import annotations

import asyncio
import os
import random
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.enums import (
    InvoiceStatus,
    InvoiceType,
    POStatus,
    SOStatus,
)
from app.models.invoice import Invoice, InvoiceLine
from app.models.master import TaxRate, UOM
from app.models.organization import Warehouse
from app.models.partner import Customer, Supplier
from app.models.purchase import PurchaseOrder, PurchaseOrderLine
from app.models.sales import SalesOrder, SalesOrderLine
from app.models.sku import SKU

log = structlog.get_logger()

ORG_ID = 1
TWO = Decimal("0.01")
FOUR = Decimal("0.0001")


def _q(d: Decimal, places: Decimal = TWO) -> Decimal:
    return d.quantize(places, rounding=ROUND_HALF_UP)


def _seasonal_weight(d: date) -> float:
    if d.year == 2026 and d.month in (3, 4):
        return 1.4
    if d.year == 2026 and d.month == 2:
        return 1.3
    if d.year == 2025 and d.month == 12:
        return 1.5
    return 1.0


def _date_range(months: int = 6) -> List[date]:
    today = date.today()
    start = today - timedelta(days=30 * months)
    days = (today - start).days
    out: List[date] = []
    for i in range(days):
        d = start + timedelta(days=i)
        weight = _seasonal_weight(d)
        # Skip Sundays half the time to mimic business cadence
        if d.weekday() == 6 and random.random() < 0.5:
            continue
        # Drop ~30% of normal days, fewer drops on heavy weighting
        if random.random() > (0.7 * weight):
            continue
        out.append(d)
    return out


async def _seed_pos(
    session: AsyncSession,
    *,
    suppliers: List[Supplier],
    warehouses: List[Warehouse],
    skus: List[SKU],
    uoms: dict[int, UOM],
    tax_rates: List[TaxRate],
    target: int,
) -> int:
    created = 0
    for i in range(target):
        biz_date = random.choice(_date_range())
        supplier = random.choice(suppliers)
        warehouse = random.choice(warehouses)
        line_count = random.randint(1, 5)
        chosen_skus = random.sample(skus, min(line_count, len(skus)))

        po = PurchaseOrder(
            organization_id=ORG_ID,
            document_no=f"PO-SEED-{i + 1:05d}",
            status=POStatus.DRAFT,
            supplier_id=supplier.id,
            warehouse_id=warehouse.id,
            business_date=biz_date,
            expected_date=biz_date + timedelta(days=random.randint(3, 14)),
            currency="MYR",
            exchange_rate=Decimal("1"),
            payment_terms_days=30,
        )
        session.add(po)
        await session.flush()

        subtotal = Decimal("0")
        tax_total = Decimal("0")
        for line_no, sku in enumerate(chosen_skus, start=1):
            tax = random.choice(tax_rates)
            qty = Decimal(random.randint(5, 50))
            unit_price = _q(Decimal(random.uniform(2, 80)), TWO)
            line_excl = _q(qty * unit_price, TWO)
            line_tax = _q(line_excl * tax.rate_percent / Decimal("100"), TWO)
            line_incl = _q(line_excl + line_tax, TWO)
            uom = uoms.get(sku.uom_id)
            if uom is None:
                continue

            session.add(
                PurchaseOrderLine(
                    purchase_order_id=po.id,
                    line_no=line_no,
                    sku_id=sku.id,
                    description=sku.name,
                    uom_id=uom.id,
                    qty_ordered=qty,
                    qty_received=Decimal("0"),
                    unit_price_excl_tax=unit_price,
                    tax_rate_id=tax.id,
                    tax_rate_percent=tax.rate_percent,
                    tax_amount=line_tax,
                    line_total_excl_tax=line_excl,
                    line_total_incl_tax=line_incl,
                )
            )
            subtotal += line_excl
            tax_total += line_tax

        po.subtotal_excl_tax = _q(subtotal, TWO)
        po.tax_amount = _q(tax_total, TWO)
        po.total_incl_tax = _q(subtotal + tax_total, TWO)
        po.base_currency_amount = po.total_incl_tax

        # Status distribution
        roll = random.random()
        if roll < 0.60:
            po.status = POStatus.FULLY_RECEIVED
        elif roll < 0.85:
            po.status = POStatus.PARTIAL_RECEIVED
        else:
            po.status = POStatus.CONFIRMED
        po.confirmed_at = datetime.combine(biz_date, datetime.min.time())

        # Reflect qty_received on lines proportionally
        if po.status == POStatus.FULLY_RECEIVED:
            for ln in po.lines:
                ln.qty_received = ln.qty_ordered
        elif po.status == POStatus.PARTIAL_RECEIVED:
            for ln in po.lines:
                ln.qty_received = _q(ln.qty_ordered * Decimal("0.5"), FOUR)

        created += 1
        if created % 50 == 0:
            await session.flush()
    return created


async def _seed_sos_and_invoices(
    session: AsyncSession,
    *,
    customers: List[Customer],
    warehouses: List[Warehouse],
    skus: List[SKU],
    uoms: dict[int, UOM],
    tax_rates: List[TaxRate],
    target: int,
) -> tuple[int, int]:
    sos_created = 0
    invoices_created = 0
    for i in range(target):
        biz_date = random.choice(_date_range())
        customer = random.choice(customers)
        warehouse = random.choice(warehouses)
        line_count = random.randint(1, 4)
        chosen_skus = random.sample(skus, min(line_count, len(skus)))

        so = SalesOrder(
            organization_id=ORG_ID,
            document_no=f"SO-SEED-{i + 1:05d}",
            status=SOStatus.DRAFT,
            customer_id=customer.id,
            warehouse_id=warehouse.id,
            business_date=biz_date,
            expected_ship_date=biz_date + timedelta(days=random.randint(1, 7)),
            currency="MYR",
            exchange_rate=Decimal("1"),
            payment_terms_days=30,
        )
        session.add(so)
        await session.flush()

        subtotal = Decimal("0")
        tax_total = Decimal("0")
        for line_no, sku in enumerate(chosen_skus, start=1):
            tax = random.choice(tax_rates)
            qty = Decimal(random.randint(1, 20))
            unit_price = _q(Decimal(random.uniform(5, 120)), TWO)
            line_excl = _q(qty * unit_price, TWO)
            line_tax = _q(line_excl * tax.rate_percent / Decimal("100"), TWO)
            line_incl = _q(line_excl + line_tax, TWO)
            uom = uoms.get(sku.uom_id)
            if uom is None:
                continue

            session.add(
                SalesOrderLine(
                    sales_order_id=so.id,
                    line_no=line_no,
                    sku_id=sku.id,
                    description=sku.name,
                    uom_id=uom.id,
                    qty_ordered=qty,
                    qty_shipped=Decimal("0"),
                    qty_invoiced=Decimal("0"),
                    unit_price_excl_tax=unit_price,
                    tax_rate_id=tax.id,
                    tax_rate_percent=tax.rate_percent,
                    tax_amount=line_tax,
                    line_total_excl_tax=line_excl,
                    line_total_incl_tax=line_incl,
                )
            )
            subtotal += line_excl
            tax_total += line_tax

        so.subtotal_excl_tax = _q(subtotal, TWO)
        so.tax_amount = _q(tax_total, TWO)
        so.total_incl_tax = _q(subtotal + tax_total, TWO)
        so.base_currency_amount = so.total_incl_tax

        roll = random.random()
        invoice_this_so = False
        if roll < 0.50:
            so.status = SOStatus.INVOICED
            invoice_this_so = True
        elif roll < 0.80:
            so.status = SOStatus.FULLY_SHIPPED
        elif roll < 0.95:
            so.status = SOStatus.CONFIRMED
        else:
            so.status = SOStatus.DRAFT

        so.confirmed_at = datetime.combine(biz_date, datetime.min.time())
        if so.status in (SOStatus.FULLY_SHIPPED, SOStatus.INVOICED):
            so.fully_shipped_at = datetime.combine(
                biz_date + timedelta(days=2), datetime.min.time()
            )
            for ln in so.lines:
                ln.qty_shipped = ln.qty_ordered
                if so.status == SOStatus.INVOICED:
                    ln.qty_invoiced = ln.qty_ordered

        sos_created += 1

        if invoice_this_so:
            inv_status_roll = random.random()
            if inv_status_roll < 0.60:
                inv_status = InvoiceStatus.FINAL
            elif inv_status_roll < 0.85:
                inv_status = InvoiceStatus.VALIDATED
            elif inv_status_roll < 0.95:
                inv_status = InvoiceStatus.SUBMITTED
            else:
                inv_status = InvoiceStatus.DRAFT

            inv = Invoice(
                organization_id=ORG_ID,
                document_no=f"INV-SEED-{i + 1:05d}",
                invoice_type=InvoiceType.INVOICE,
                status=inv_status,
                sales_order_id=so.id,
                customer_id=customer.id,
                business_date=so.fully_shipped_at.date() if so.fully_shipped_at else biz_date,
                currency="MYR",
                exchange_rate=Decimal("1"),
                subtotal_excl_tax=so.subtotal_excl_tax,
                tax_amount=so.tax_amount,
                total_incl_tax=so.total_incl_tax,
                base_currency_amount=so.total_incl_tax,
                seller_tin="EI00000000010",
                buyer_tin=getattr(customer, "tin", None) or "EI00000000010",
            )
            if inv_status in (InvoiceStatus.SUBMITTED, InvoiceStatus.VALIDATED, InvoiceStatus.FINAL):
                inv.uin = f"INV-{random.randint(10000000, 99999999)}-DEMO"
                inv.submitted_at = datetime.combine(biz_date + timedelta(days=2), datetime.min.time())
                inv.validated_at = inv.submitted_at + timedelta(minutes=5)
            if inv_status == InvoiceStatus.FINAL:
                inv.finalized_at = inv.validated_at + timedelta(hours=72)
            session.add(inv)
            await session.flush()

            for line_no, sol in enumerate(so.lines, start=1):
                session.add(
                    InvoiceLine(
                        invoice_id=inv.id,
                        line_no=line_no,
                        sales_order_line_id=sol.id,
                        sku_id=sol.sku_id,
                        description=sol.description,
                        qty=sol.qty_ordered,
                        uom_id=sol.uom_id,
                        unit_price_excl_tax=sol.unit_price_excl_tax,
                        tax_rate_id=sol.tax_rate_id,
                        tax_rate_percent=sol.tax_rate_percent,
                        tax_amount=sol.tax_amount,
                        line_total_excl_tax=sol.line_total_excl_tax,
                        line_total_incl_tax=sol.line_total_incl_tax,
                    )
                )
            invoices_created += 1

        if (i + 1) % 50 == 0:
            await session.flush()
    return sos_created, invoices_created


async def seed_transactional(session: AsyncSession) -> dict[str, int]:
    """Public entry point — also called from app.services.demo_reset."""
    suppliers = (
        (await session.execute(select(Supplier).where(Supplier.deleted_at.is_(None))))
        .scalars()
        .all()
    )
    customers = (
        (await session.execute(select(Customer).where(Customer.deleted_at.is_(None))))
        .scalars()
        .all()
    )
    warehouses = (
        (await session.execute(select(Warehouse).where(Warehouse.deleted_at.is_(None))))
        .scalars()
        .all()
    )
    skus = (
        (await session.execute(select(SKU).where(SKU.deleted_at.is_(None))))
        .scalars()
        .all()
    )
    uom_rows = (await session.execute(select(UOM))).scalars().all()
    uoms = {u.id: u for u in uom_rows}
    tax_rates = (await session.execute(select(TaxRate))).scalars().all()

    if not (suppliers and customers and warehouses and skus and tax_rates):
        log.warning(
            "seed_transactional_skipped_missing_master",
            suppliers=len(suppliers),
            customers=len(customers),
            warehouses=len(warehouses),
            skus=len(skus),
            tax_rates=len(tax_rates),
        )
        return {"po": 0, "so": 0, "invoice": 0}

    pos = await _seed_pos(
        session,
        suppliers=list(suppliers),
        warehouses=list(warehouses),
        skus=list(skus),
        uoms=uoms,
        tax_rates=list(tax_rates),
        target=150,
    )
    sos, invs = await _seed_sos_and_invoices(
        session,
        customers=list(customers),
        warehouses=list(warehouses),
        skus=list(skus),
        uoms=uoms,
        tax_rates=list(tax_rates),
        target=250,
    )

    log.info("seed_transactional_done", po=pos, so=sos, invoice=invs)
    return {"po": pos, "so": sos, "invoice": invs}


async def main() -> None:
    import logging

    logging.basicConfig(level=logging.INFO)
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionLocal() as session:
        async with session.begin():
            stats = await seed_transactional(session)
    await engine.dispose()
    print(f"\n✅ Transactional seed complete — {stats}")


if __name__ == "__main__":
    asyncio.run(main())
