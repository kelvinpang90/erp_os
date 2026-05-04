"""Reports service — 10 aggregation queries powering the Reports centre.

Strategy: pure SQLAlchemy aggregations against the existing tables, scoped
to the caller's organisation and a date window. The router caches each
result in Redis DB 1 with a 5-minute TTL keyed by (org_id, function, days);
the cache invalidation handler in events/handlers/cache.py wipes the
``dashboard:{org}:reports:*`` namespace when stock movements or document
status changes land.

Each function returns a Pydantic response model — never an ORM row.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import case, func, literal, select, type_coerce
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import Numeric

from app.enums import (
    AIFeature,
    InvoiceStatus,
    POStatus,
    SOStatus,
    StockMovementType,
)
from app.models.audit import AICallLog
from app.models.invoice import Invoice
from app.models.master import Category
from app.models.organization import Warehouse
from app.models.partner import Customer, Supplier
from app.models.purchase import PurchaseOrder, PurchaseOrderLine
from app.models.sales import SalesOrder, SalesOrderLine
from app.models.sku import SKU
from app.models.stock import Stock, StockMovement
from app.schemas.dashboard import (
    AICostMetricsResponse,
    CategoryShareResponse,
    CategoryShareRow,
    EInvoiceStatusDistributionResponse,
    FeatureCostRow,
    InventoryTurnoverResponse,
    InventoryTurnoverRow,
    StatusBucket,
    TopEntityResponse,
    TopEntityRow,
    TrendPoint,
    TrendSeriesResponse,
    WarehouseStockDistributionResponse,
    WarehouseStockRow,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _today() -> date:
    return datetime.now(UTC).date()


def _window(days: int) -> tuple[date, date]:
    """Closed-open window [start, end_exclusive)."""
    end = _today() + timedelta(days=1)
    start = end - timedelta(days=days)
    return start, end


def _zero_filled_series(
    rows: list[tuple[date, Decimal]],
    days: int,
) -> list[TrendPoint]:
    """Backfill missing dates with Decimal('0') so charts don't gap.

    Inputs are (date, value) tuples already aggregated in SQL. Zero-filling
    in Python is simpler and faster than CTE date series for this volume.
    """
    by_date = {d: v or Decimal("0") for d, v in rows}
    end = _today()
    start = end - timedelta(days=days - 1)
    out: list[TrendPoint] = []
    cursor = start
    while cursor <= end:
        out.append(TrendPoint(bucket=cursor, value=by_date.get(cursor, Decimal("0"))))
        cursor = cursor + timedelta(days=1)
    return out


# ── 1. Sales trend ────────────────────────────────────────────────────────────


async def get_sales_trend(
    session: AsyncSession,
    *,
    organization_id: int,
    days: int = 30,
) -> TrendSeriesResponse:
    """Daily SUM(SO.total_incl_tax) over the trailing ``days`` window.

    Excludes cancelled / draft orders — only confirmed-or-later count toward
    revenue. Soft-deleted SOs filtered out via deleted_at.
    """
    start, end = _window(days)
    bucket = func.date(SalesOrder.business_date).label("bucket")
    stmt = (
        select(bucket, func.coalesce(func.sum(SalesOrder.total_incl_tax), 0))
        .where(
            SalesOrder.organization_id == organization_id,
            SalesOrder.deleted_at.is_(None),
            SalesOrder.business_date >= start,
            SalesOrder.business_date < end,
            SalesOrder.status.notin_([SOStatus.DRAFT, SOStatus.CANCELLED]),
        )
        .group_by(bucket)
        .order_by(bucket)
    )
    rows = [(r[0], Decimal(r[1] or 0)) for r in (await session.execute(stmt)).all()]
    points = _zero_filled_series(rows, days)
    total = sum((p.value for p in points), Decimal("0"))
    return TrendSeriesResponse(points=points, total=total, days=days)


# ── 2. Purchase trend ─────────────────────────────────────────────────────────


async def get_purchase_trend(
    session: AsyncSession,
    *,
    organization_id: int,
    days: int = 30,
) -> TrendSeriesResponse:
    """Daily SUM(PO.total_incl_tax). Mirrors sales-trend semantics."""
    start, end = _window(days)
    bucket = func.date(PurchaseOrder.business_date).label("bucket")
    stmt = (
        select(bucket, func.coalesce(func.sum(PurchaseOrder.total_incl_tax), 0))
        .where(
            PurchaseOrder.organization_id == organization_id,
            PurchaseOrder.deleted_at.is_(None),
            PurchaseOrder.business_date >= start,
            PurchaseOrder.business_date < end,
            PurchaseOrder.status.notin_([POStatus.DRAFT, POStatus.CANCELLED]),
        )
        .group_by(bucket)
        .order_by(bucket)
    )
    rows = [(r[0], Decimal(r[1] or 0)) for r in (await session.execute(stmt)).all()]
    points = _zero_filled_series(rows, days)
    total = sum((p.value for p in points), Decimal("0"))
    return TrendSeriesResponse(points=points, total=total, days=days)


# ── 3. Top SKUs by sales ──────────────────────────────────────────────────────


async def get_top_skus_by_sales(
    session: AsyncSession,
    *,
    organization_id: int,
    days: int = 30,
    limit: int = 10,
) -> TopEntityResponse:
    """Top N SKUs by SOLine.line_total_incl_tax over the window."""
    start, end = _window(days)
    qty_sum = func.coalesce(func.sum(SalesOrderLine.qty_ordered), 0)
    amount_sum = func.coalesce(func.sum(SalesOrderLine.line_total_incl_tax), 0)
    stmt = (
        select(SKU.id, SKU.code, SKU.name, SKU.name_zh, qty_sum, amount_sum)
        .join(SalesOrderLine, SalesOrderLine.sku_id == SKU.id)
        .join(SalesOrder, SalesOrder.id == SalesOrderLine.sales_order_id)
        .where(
            SalesOrder.organization_id == organization_id,
            SalesOrder.deleted_at.is_(None),
            SalesOrder.business_date >= start,
            SalesOrder.business_date < end,
            SalesOrder.status.notin_([SOStatus.DRAFT, SOStatus.CANCELLED]),
        )
        .group_by(SKU.id, SKU.code, SKU.name, SKU.name_zh)
        .order_by(amount_sum.desc())
        .limit(limit)
    )
    rows: list[TopEntityRow] = []
    for sku_id, code, name, name_zh, qty, amount in (await session.execute(stmt)).all():
        rows.append(
            TopEntityRow(
                id=sku_id,
                code=code,
                name=name,
                name_zh=name_zh,
                qty=Decimal(qty or 0),
                amount=Decimal(amount or 0),
            )
        )
    return TopEntityResponse(rows=rows, days=days)


# ── 4. Top suppliers by purchase ──────────────────────────────────────────────


async def get_top_suppliers_by_purchase(
    session: AsyncSession,
    *,
    organization_id: int,
    days: int = 30,
    limit: int = 10,
) -> TopEntityResponse:
    """Top N suppliers by PO.total_incl_tax over the window."""
    start, end = _window(days)
    amount_sum = func.coalesce(func.sum(PurchaseOrder.total_incl_tax), 0)
    po_count = func.count(PurchaseOrder.id)
    stmt = (
        select(Supplier.id, Supplier.code, Supplier.name, po_count, amount_sum)
        .join(PurchaseOrder, PurchaseOrder.supplier_id == Supplier.id)
        .where(
            PurchaseOrder.organization_id == organization_id,
            PurchaseOrder.deleted_at.is_(None),
            PurchaseOrder.business_date >= start,
            PurchaseOrder.business_date < end,
            PurchaseOrder.status.notin_([POStatus.DRAFT, POStatus.CANCELLED]),
        )
        .group_by(Supplier.id, Supplier.code, Supplier.name)
        .order_by(amount_sum.desc())
        .limit(limit)
    )
    rows: list[TopEntityRow] = []
    for sup_id, code, name, count, amount in (await session.execute(stmt)).all():
        rows.append(
            TopEntityRow(
                id=sup_id,
                code=code,
                name=name,
                qty=Decimal(count or 0),  # repurpose qty as PO count
                amount=Decimal(amount or 0),
            )
        )
    return TopEntityResponse(rows=rows, days=days)


# ── 5. Top customers by revenue ───────────────────────────────────────────────


async def get_top_customers_by_revenue(
    session: AsyncSession,
    *,
    organization_id: int,
    days: int = 30,
    limit: int = 10,
) -> TopEntityResponse:
    """Top N customers by SO.total_incl_tax over the window."""
    start, end = _window(days)
    amount_sum = func.coalesce(func.sum(SalesOrder.total_incl_tax), 0)
    so_count = func.count(SalesOrder.id)
    stmt = (
        select(Customer.id, Customer.code, Customer.name, so_count, amount_sum)
        .join(SalesOrder, SalesOrder.customer_id == Customer.id)
        .where(
            SalesOrder.organization_id == organization_id,
            SalesOrder.deleted_at.is_(None),
            SalesOrder.business_date >= start,
            SalesOrder.business_date < end,
            SalesOrder.status.notin_([SOStatus.DRAFT, SOStatus.CANCELLED]),
        )
        .group_by(Customer.id, Customer.code, Customer.name)
        .order_by(amount_sum.desc())
        .limit(limit)
    )
    rows: list[TopEntityRow] = []
    for cust_id, code, name, count, amount in (await session.execute(stmt)).all():
        rows.append(
            TopEntityRow(
                id=cust_id,
                code=code,
                name=name,
                qty=Decimal(count or 0),
                amount=Decimal(amount or 0),
            )
        )
    return TopEntityResponse(rows=rows, days=days)


# ── 6. Inventory turnover ─────────────────────────────────────────────────────


async def get_inventory_turnover(
    session: AsyncSession,
    *,
    organization_id: int,
    days: int = 30,
    limit: int = 20,
) -> InventoryTurnoverResponse:
    """Top SKUs by COGS (proxy for turnover) over the window.

    Simplified turnover = COGS_window / current_inventory_value.
    Avg inventory uses the current snapshot rather than period-average to
    keep the query single-pass; for demo data sizes the bias is acceptable.
    """
    start, end = _window(days)

    cogs_expr = func.coalesce(
        func.sum(StockMovement.quantity * StockMovement.unit_cost),
        0,
    ).label("cogs")
    inv_value_expr = func.coalesce(
        func.sum(Stock.on_hand * Stock.avg_cost), 0,
    )

    cogs_stmt = (
        select(SKU.id, SKU.code, SKU.name, cogs_expr)
        .join(StockMovement, StockMovement.sku_id == SKU.id)
        .where(
            StockMovement.organization_id == organization_id,
            StockMovement.movement_type == StockMovementType.SALES_OUT,
            StockMovement.occurred_at >= start,
            StockMovement.occurred_at < end,
        )
        .group_by(SKU.id, SKU.code, SKU.name)
        .order_by(cogs_expr.desc())
        .limit(limit)
    )
    cogs_rows = (await session.execute(cogs_stmt)).all()

    if not cogs_rows:
        return InventoryTurnoverResponse(rows=[], days=days)

    sku_ids = [r[0] for r in cogs_rows]
    inv_stmt = (
        select(Stock.sku_id, inv_value_expr.label("inv_value"))
        .where(
            Stock.organization_id == organization_id,
            Stock.sku_id.in_(sku_ids),
        )
        .group_by(Stock.sku_id)
    )
    inv_value_by_sku = {
        sku_id: Decimal(v or 0) for sku_id, v in (await session.execute(inv_stmt)).all()
    }

    rows: list[InventoryTurnoverRow] = []
    for sku_id, code, name, cogs in cogs_rows:
        cogs_dec = Decimal(cogs or 0)
        inv_val = inv_value_by_sku.get(sku_id, Decimal("0"))
        ratio = (cogs_dec / inv_val) if inv_val > 0 else Decimal("0")
        rows.append(
            InventoryTurnoverRow(
                sku_id=sku_id,
                sku_code=code,
                sku_name=name,
                cogs=cogs_dec,
                avg_inventory_value=inv_val,
                turnover_ratio=ratio.quantize(Decimal("0.01")),
            )
        )
    return InventoryTurnoverResponse(rows=rows, days=days)


# ── 7. Warehouse stock distribution ───────────────────────────────────────────


async def get_warehouse_stock_distribution(
    session: AsyncSession,
    *,
    organization_id: int,
) -> WarehouseStockDistributionResponse:
    """Total inventory value per warehouse — for the pie/bar chart."""
    value_expr = func.coalesce(func.sum(Stock.on_hand * Stock.avg_cost), 0).label("value")
    sku_count_expr = func.count(case((Stock.on_hand > 0, Stock.sku_id))).label("sku_count")

    stmt = (
        select(
            Warehouse.id,
            Warehouse.code,
            Warehouse.name,
            value_expr,
            sku_count_expr,
        )
        .outerjoin(Stock, Stock.warehouse_id == Warehouse.id)
        .where(
            Warehouse.organization_id == organization_id,
            Warehouse.deleted_at.is_(None),
            Warehouse.is_active.is_(True),
        )
        .group_by(Warehouse.id, Warehouse.code, Warehouse.name)
        .order_by(value_expr.desc())
    )
    rows: list[WarehouseStockRow] = []
    total = Decimal("0")
    for wh_id, code, name, value, sku_count in (await session.execute(stmt)).all():
        v = Decimal(value or 0)
        total += v
        rows.append(
            WarehouseStockRow(
                warehouse_id=wh_id,
                warehouse_code=code,
                warehouse_name=name,
                on_hand_value=v,
                sku_count=int(sku_count or 0),
            )
        )
    return WarehouseStockDistributionResponse(rows=rows, total_value=total)


# ── 8. Category sales share ───────────────────────────────────────────────────


async def get_category_sales_share(
    session: AsyncSession,
    *,
    organization_id: int,
    days: int = 30,
) -> CategoryShareResponse:
    """SUM(SOLine.line_total_incl_tax) by SKU.category — donut data."""
    start, end = _window(days)
    amount_sum = func.coalesce(func.sum(SalesOrderLine.line_total_incl_tax), 0).label("amt")
    stmt = (
        select(Category.id, Category.name, amount_sum)
        .select_from(SalesOrderLine)
        .join(SalesOrder, SalesOrder.id == SalesOrderLine.sales_order_id)
        .join(SKU, SKU.id == SalesOrderLine.sku_id)
        .outerjoin(Category, Category.id == SKU.category_id)
        .where(
            SalesOrder.organization_id == organization_id,
            SalesOrder.deleted_at.is_(None),
            SalesOrder.business_date >= start,
            SalesOrder.business_date < end,
            SalesOrder.status.notin_([SOStatus.DRAFT, SOStatus.CANCELLED]),
        )
        .group_by(Category.id, Category.name)
        .order_by(amount_sum.desc())
    )
    raw = list((await session.execute(stmt)).all())
    total = sum((Decimal(r[2] or 0) for r in raw), Decimal("0"))
    rows: list[CategoryShareRow] = []
    for cat_id, name, amount in raw:
        amount_dec = Decimal(amount or 0)
        share = (amount_dec / total * 100) if total > 0 else Decimal("0")
        rows.append(
            CategoryShareRow(
                category_id=cat_id,
                category_name=name or "Uncategorized",
                amount=amount_dec,
                share_pct=share.quantize(Decimal("0.01")),
            )
        )
    return CategoryShareResponse(rows=rows, total=total, days=days)


# ── 9. e-Invoice status distribution ──────────────────────────────────────────


async def get_einvoice_status_distribution(
    session: AsyncSession,
    *,
    organization_id: int,
    days: Optional[int] = 30,
) -> EInvoiceStatusDistributionResponse:
    """Count of invoices grouped by status, optionally constrained to the window."""
    filters = [
        Invoice.organization_id == organization_id,
        Invoice.deleted_at.is_(None),
    ]
    if days:
        start, end = _window(days)
        filters.append(Invoice.business_date >= start)
        filters.append(Invoice.business_date < end)

    count_expr = func.count(Invoice.id)
    stmt = (
        select(Invoice.status, count_expr)
        .where(*filters)
        .group_by(Invoice.status)
        .order_by(count_expr.desc())
    )
    rows = [
        StatusBucket(status=s.value if hasattr(s, "value") else str(s), count=int(c))
        for s, c in (await session.execute(stmt)).all()
    ]
    total = sum(r.count for r in rows)
    return EInvoiceStatusDistributionResponse(rows=rows, total=total)


# ── 10. AI cost metrics ───────────────────────────────────────────────────────


async def get_ai_cost_metrics(
    session: AsyncSession,
    *,
    organization_id: int,
    days: int = 30,
) -> AICostMetricsResponse:
    """Daily AI spend + per-feature breakdown over the window."""
    start, end = _window(days)

    bucket = func.date(AICallLog.created_at).label("bucket")
    daily_stmt = (
        select(bucket, func.coalesce(func.sum(AICallLog.cost_usd), 0))
        .where(
            AICallLog.organization_id == organization_id,
            AICallLog.created_at >= start,
            AICallLog.created_at < end,
        )
        .group_by(bucket)
        .order_by(bucket)
    )
    daily_rows = [
        (r[0], Decimal(r[1] or 0)) for r in (await session.execute(daily_stmt)).all()
    ]
    points = _zero_filled_series(daily_rows, days)

    feature_stmt = (
        select(
            AICallLog.feature,
            func.count(AICallLog.id),
            func.coalesce(func.sum(AICallLog.cost_usd), 0),
        )
        .where(
            AICallLog.organization_id == organization_id,
            AICallLog.created_at >= start,
            AICallLog.created_at < end,
        )
        .group_by(AICallLog.feature)
    )
    feature_rows = [
        FeatureCostRow(
            feature=f.value if hasattr(f, "value") else str(f),
            calls=int(c),
            cost_usd=Decimal(s or 0),
        )
        for f, c, s in (await session.execute(feature_stmt)).all()
    ]
    total_cost = sum((r.cost_usd for r in feature_rows), Decimal("0"))
    total_calls = sum(r.calls for r in feature_rows)

    return AICostMetricsResponse(
        series=points,
        total_cost_usd=total_cost,
        total_calls=total_calls,
        by_feature=feature_rows,
        days=days,
    )
