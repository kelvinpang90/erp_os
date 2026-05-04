"""Dashboard + Reports response schemas (Window 15).

Dashboard /overview returns a single payload combining KPIs, the AI
summary, and small inline trend series so the homepage can render in a
single round-trip. Reports endpoints each return their own focused shape.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


_cfg = ConfigDict(from_attributes=True, json_encoders={Decimal: str})


# ── KPI cards ─────────────────────────────────────────────────────────────────


class DashboardKPIs(BaseModel):
    today_sales: Decimal              # SUM(SO.total_incl_tax) where business_date = today
    today_purchases: Decimal          # SUM(PO.total_incl_tax) where business_date = today
    pending_shipments: int            # SO confirmed/partial_shipped count
    low_stock_count: int              # (sku, warehouse) pairs with available < safety_stock
    pending_einvoices: int            # invoice status DRAFT or SUBMITTED
    ai_cost_today_usd: Decimal        # SUM(ai_call_logs.cost_usd) where DATE(created_at)=today

    model_config = _cfg


# ── AI summary ────────────────────────────────────────────────────────────────


class AISummaryPayload(BaseModel):
    """Body of the AI-generated daily digest."""

    headline: str
    key_findings: List[str]
    action_items: List[str]

    model_config = _cfg


class AISummaryEnvelope(BaseModel):
    """Wrapper that adds freshness / availability metadata for the UI."""

    available: bool                                # AI gate enabled & at least one summary exists
    payload: Optional[AISummaryPayload] = None     # None when degraded with no cached fallback
    is_stale: bool = False                         # True when the cached body is past TTL
    staleness_seconds: int = 0                     # How old the cached body is
    generated_at: Optional[datetime] = None
    error_code: Optional[str] = None               # AI_DISABLED / AI_TIMEOUT / AI_ERROR / NEVER_GENERATED

    model_config = _cfg


# ── Trend series ──────────────────────────────────────────────────────────────


class TrendPoint(BaseModel):
    """One point in a date-bucketed trend series."""

    bucket: date
    value: Decimal

    model_config = _cfg


class CountTrendPoint(BaseModel):
    bucket: date
    value: int

    model_config = _cfg


class DashboardTrends(BaseModel):
    sales_last_30d: List[TrendPoint]
    purchase_last_30d: List[TrendPoint]
    einvoice_status_distribution: List["StatusBucket"]
    ai_cost_last_30d: List[TrendPoint]

    model_config = _cfg


class StatusBucket(BaseModel):
    status: str
    count: int

    model_config = _cfg


class DashboardOverviewResponse(BaseModel):
    kpis: DashboardKPIs
    summary: AISummaryEnvelope
    trends: DashboardTrends
    cache_hit: bool = False
    refreshed_at: datetime

    model_config = _cfg


# ── Reports schemas ───────────────────────────────────────────────────────────


class TrendSeriesResponse(BaseModel):
    """Generic time-series payload (sales / purchase / ai cost)."""

    points: List[TrendPoint]
    total: Decimal
    days: int

    model_config = _cfg


class TopEntityRow(BaseModel):
    """Top-N leaderboard row used by SKU / supplier / customer rankings."""

    id: int
    code: str
    name: str
    name_zh: Optional[str] = None
    qty: Decimal = Decimal("0")
    amount: Decimal = Decimal("0")

    model_config = _cfg


class TopEntityResponse(BaseModel):
    rows: List[TopEntityRow]
    days: int

    model_config = _cfg


class CategoryShareRow(BaseModel):
    category_id: Optional[int]
    category_name: str
    amount: Decimal
    share_pct: Decimal  # 0..100

    model_config = _cfg


class CategoryShareResponse(BaseModel):
    rows: List[CategoryShareRow]
    total: Decimal
    days: int

    model_config = _cfg


class WarehouseStockRow(BaseModel):
    warehouse_id: int
    warehouse_code: str
    warehouse_name: str
    on_hand_value: Decimal           # SUM(on_hand * avg_cost)
    sku_count: int                   # distinct SKUs with on_hand > 0

    model_config = _cfg


class WarehouseStockDistributionResponse(BaseModel):
    rows: List[WarehouseStockRow]
    total_value: Decimal

    model_config = _cfg


class InventoryTurnoverRow(BaseModel):
    sku_id: int
    sku_code: str
    sku_name: str
    cogs: Decimal                    # SUM(SALES_OUT.qty * unit_cost) over window
    avg_inventory_value: Decimal     # snapshot (on_hand * avg_cost) — simplified
    turnover_ratio: Decimal          # cogs / avg_inventory_value, 0 when denominator missing

    model_config = _cfg


class InventoryTurnoverResponse(BaseModel):
    rows: List[InventoryTurnoverRow]
    days: int

    model_config = _cfg


class EInvoiceStatusDistributionResponse(BaseModel):
    rows: List[StatusBucket]
    total: int

    model_config = _cfg


class AICostMetricsResponse(BaseModel):
    series: List[TrendPoint]         # daily cost
    total_cost_usd: Decimal
    total_calls: int
    by_feature: List["FeatureCostRow"]
    days: int

    model_config = _cfg


class FeatureCostRow(BaseModel):
    feature: str
    calls: int
    cost_usd: Decimal

    model_config = _cfg


# Forward refs
DashboardTrends.model_rebuild()
AICostMetricsResponse.model_rebuild()
