"""Dashboard service — KPIs, AI daily summary, and combined overview.

The /api/dashboard/overview endpoint returns everything the homepage needs
in one round-trip: 5 KPI cards, an AI-generated digest, and four small
trend series. Each piece is cached independently in Redis DB 1:

  dashboard:{org}:kpi          TTL 5min   – cheap aggregations
  dashboard:{org}:trends       TTL 5min   – four small series
  dashboard:{org}:summary      TTL 30min  – AI-generated digest body
  dashboard:{org}:summary:meta TTL 30min  – generation timestamp + status

Cache invalidation: events/handlers/cache.py listens on the three core
domain events (StockMovementOccurred, DocumentStatusChanged,
EInvoiceValidated) and DELs the kpi/trends keys. AI summary is left alone
so we don't burn LLM tokens on every stock move; its 30-min TTL is the
freshness budget.

AI summary generation is **lazy** (per the W15 plan):
  * Cache hit  → return immediately, mark fresh.
  * Cache miss → kick off a fire-and-forget background task and return
    whatever stale body we have plus a placeholder otherwise.
  * Admin can call /summary/refresh to force regeneration synchronously.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional

import structlog
from anthropic import AsyncAnthropic
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.logging import get_request_id
from app.core.redis import redis_cache
from app.enums import (
    AICallStatus,
    AIFeature,
    InvoiceStatus,
    POStatus,
    SOStatus,
)
from app.models.audit import AICallLog
from app.models.invoice import Invoice
from app.models.purchase import PurchaseOrder
from app.models.sales import SalesOrder
from app.models.sku import SKU
from app.models.stock import Stock
from app.schemas.dashboard import (
    AISummaryEnvelope,
    AISummaryPayload,
    DashboardKPIs,
    DashboardOverviewResponse,
    DashboardTrends,
)
from app.services import reports as reports_service
from app.services.ai_gate import AIFeatureGate
from app.services.prompts import load_prompt

log = structlog.get_logger(__name__)


# ── Cache settings ────────────────────────────────────────────────────────────


_KPI_TTL_SECONDS = 300        # 5 min
_TRENDS_TTL_SECONDS = 300     # 5 min
_SUMMARY_TTL_SECONDS = 1800   # 30 min – also the staleness threshold
_SUMMARY_GENERATION_TIMEOUT = 8.0  # seconds; AI call hard cap


def _kpi_key(org_id: int) -> str:
    return f"dashboard:{org_id}:kpi"


def _trends_key(org_id: int) -> str:
    return f"dashboard:{org_id}:trends"


# NOTE: ":v2" suffix marks the bilingual schema (en + zh in one payload).
# Old single-language v1 cache entries simply expire in their TTL window.
def _summary_key(org_id: int) -> str:
    return f"dashboard:{org_id}:summary:v2"


def _summary_meta_key(org_id: int) -> str:
    return f"dashboard:{org_id}:summary:meta:v2"


def _summary_lock_key(org_id: int) -> str:
    return f"dashboard:{org_id}:summary:lock:v2"


# Track in-flight summary generations so the lazy path doesn't fan out one
# task per concurrent request.
_in_flight_summary_tasks: set[int] = set()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _today() -> date:
    return datetime.now(UTC).date()


def _utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


_JSON_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.MULTILINE)


def _strip_json_fences(text: str) -> str:
    return _JSON_FENCE_RE.sub("", text).strip()


_PRICING_USD_PER_MTOK: dict[str, tuple[Decimal, Decimal]] = {
    "claude-sonnet-4-6": (Decimal("3.00"), Decimal("15.00")),
    "claude-opus-4-7": (Decimal("15.00"), Decimal("75.00")),
    "claude-haiku-4-5-20251001": (Decimal("0.80"), Decimal("4.00")),
}
_DEFAULT_PRICING: tuple[Decimal, Decimal] = (Decimal("3.00"), Decimal("15.00"))


def _calc_cost_usd(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    in_rate, out_rate = _PRICING_USD_PER_MTOK.get(model, _DEFAULT_PRICING)
    cost = (
        Decimal(input_tokens) * in_rate + Decimal(output_tokens) * out_rate
    ) / Decimal(1_000_000)
    return cost.quantize(Decimal("0.000001"))


# ── KPI computation ───────────────────────────────────────────────────────────


async def get_kpi_overview(
    session: AsyncSession,
    *,
    organization_id: int,
) -> DashboardKPIs:
    """Five-figure ops snapshot for the KPI cards."""
    today = _today()

    # 1. Today's sales (confirmed-or-later, business_date = today)
    sales_stmt = select(
        func.coalesce(func.sum(SalesOrder.total_incl_tax), 0)
    ).where(
        SalesOrder.organization_id == organization_id,
        SalesOrder.deleted_at.is_(None),
        SalesOrder.business_date == today,
        SalesOrder.status.notin_([SOStatus.DRAFT, SOStatus.CANCELLED]),
    )
    today_sales = Decimal((await session.execute(sales_stmt)).scalar_one() or 0)

    # 2. Today's purchases
    purchase_stmt = select(
        func.coalesce(func.sum(PurchaseOrder.total_incl_tax), 0)
    ).where(
        PurchaseOrder.organization_id == organization_id,
        PurchaseOrder.deleted_at.is_(None),
        PurchaseOrder.business_date == today,
        PurchaseOrder.status.notin_([POStatus.DRAFT, POStatus.CANCELLED]),
    )
    today_purchases = Decimal(
        (await session.execute(purchase_stmt)).scalar_one() or 0
    )

    # 3. Pending shipments — SO confirmed or partially shipped
    pending_ship_stmt = select(func.count(SalesOrder.id)).where(
        SalesOrder.organization_id == organization_id,
        SalesOrder.deleted_at.is_(None),
        SalesOrder.status.in_([SOStatus.CONFIRMED, SOStatus.PARTIAL_SHIPPED]),
    )
    pending_shipments = int(
        (await session.execute(pending_ship_stmt)).scalar_one() or 0
    )

    # 4. Low-stock count — distinct (sku, warehouse) where available < safety_stock
    available_expr = Stock.on_hand - Stock.reserved - Stock.quality_hold
    low_stock_stmt = (
        select(func.count())
        .select_from(Stock)
        .join(SKU, SKU.id == Stock.sku_id)
        .where(
            Stock.organization_id == organization_id,
            SKU.deleted_at.is_(None),
            SKU.is_active.is_(True),
            SKU.safety_stock > 0,
            available_expr < SKU.safety_stock,
        )
    )
    low_stock_count = int((await session.execute(low_stock_stmt)).scalar_one() or 0)

    # 5. Pending e-Invoices — DRAFT or SUBMITTED
    pending_inv_stmt = select(func.count(Invoice.id)).where(
        Invoice.organization_id == organization_id,
        Invoice.deleted_at.is_(None),
        Invoice.status.in_([InvoiceStatus.DRAFT, InvoiceStatus.SUBMITTED]),
    )
    pending_einvoices = int(
        (await session.execute(pending_inv_stmt)).scalar_one() or 0
    )

    # 6. Today's AI cost
    ai_cost_stmt = select(
        func.coalesce(func.sum(AICallLog.cost_usd), 0)
    ).where(
        AICallLog.organization_id == organization_id,
        func.date(AICallLog.created_at) == today,
    )
    ai_cost_today = Decimal(
        (await session.execute(ai_cost_stmt)).scalar_one() or 0
    )

    return DashboardKPIs(
        today_sales=today_sales,
        today_purchases=today_purchases,
        pending_shipments=pending_shipments,
        low_stock_count=low_stock_count,
        pending_einvoices=pending_einvoices,
        ai_cost_today_usd=ai_cost_today.quantize(Decimal("0.000001")),
    )


# ── Trend series for the dashboard ────────────────────────────────────────────


async def get_dashboard_trends(
    session: AsyncSession,
    *,
    organization_id: int,
) -> DashboardTrends:
    """Four small inline series for the homepage trend cards."""
    sales = await reports_service.get_sales_trend(
        session, organization_id=organization_id, days=30
    )
    purchase = await reports_service.get_purchase_trend(
        session, organization_id=organization_id, days=30
    )
    einvoice_dist = await reports_service.get_einvoice_status_distribution(
        session, organization_id=organization_id, days=30
    )
    ai_cost = await reports_service.get_ai_cost_metrics(
        session, organization_id=organization_id, days=30
    )

    return DashboardTrends(
        sales_last_30d=sales.points,
        purchase_last_30d=purchase.points,
        einvoice_status_distribution=einvoice_dist.rows,
        ai_cost_last_30d=ai_cost.series,
    )


# ── AI summary (lazy + cached) ────────────────────────────────────────────────


async def _generate_ai_summary(
    *,
    organization_id: int,
    user_id: Optional[int] = None,
) -> tuple[Optional[AISummaryPayload], AICallStatus, Optional[str]]:
    """Synchronous LLM call. Used by the foreground refresh and the
    background lazy task. Always returns even on failure — the caller
    decides whether to fall back to a stale body.
    """
    prompt = load_prompt("dashboard_summary")
    model = prompt.model

    # Pull a fresh KPI / trend snapshot in a dedicated session so we don't
    # piggyback on a request session whose lifetime we don't control.
    async with AsyncSessionLocal() as snapshot_session:
        kpis = await get_kpi_overview(
            snapshot_session, organization_id=organization_id
        )
        sales = await reports_service.get_sales_trend(
            snapshot_session, organization_id=organization_id, days=7
        )

    pending = {
        "pending_shipments": kpis.pending_shipments,
        "low_stock_count": kpis.low_stock_count,
        "pending_einvoices": kpis.pending_einvoices,
    }
    user_message = prompt.user_template.format(
        today_iso=_today().isoformat(),
        kpi_json=json.dumps(
            {
                "today_sales_rm": str(kpis.today_sales),
                "today_purchases_rm": str(kpis.today_purchases),
                **pending,
                "ai_cost_today_usd": str(kpis.ai_cost_today_usd),
            },
            ensure_ascii=False,
        ),
        sales_trend_json=json.dumps(
            [{p.bucket.isoformat(): str(p.value)} for p in sales.points],
            ensure_ascii=False,
        ),
        pending_json=json.dumps(pending, ensure_ascii=False),
    )

    started = time.monotonic()
    status = AICallStatus.FAILURE
    error_code: Optional[str] = None
    input_tokens = 0
    output_tokens = 0
    payload: Optional[AISummaryPayload] = None

    client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    try:
        response = await asyncio.wait_for(
            client.messages.create(
                model=model,
                system=prompt.system,
                temperature=prompt.temperature,
                max_tokens=prompt.max_tokens,
                messages=[{"role": "user", "content": user_message}],
            ),
            timeout=_SUMMARY_GENERATION_TIMEOUT,
        )
        input_tokens = int(getattr(response.usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(response.usage, "output_tokens", 0) or 0)
        text_blocks = [
            b.text for b in response.content if getattr(b, "type", None) == "text"
        ]
        if not text_blocks:
            error_code = "EMPTY_LLM_RESPONSE"
        else:
            try:
                raw = _strip_json_fences("\n".join(text_blocks))
                parsed = json.loads(raw)
                payload = AISummaryPayload.model_validate(parsed)
                status = AICallStatus.SUCCESS
            except (json.JSONDecodeError, ValueError) as e:
                error_code = "LLM_SCHEMA_MISMATCH"
                log.warning("dashboard.summary.parse_failed", err=str(e))

    except asyncio.TimeoutError:
        status = AICallStatus.TIMEOUT
        error_code = "AI_TIMEOUT"
        log.warning("dashboard.summary.timeout", organization_id=organization_id)
    except Exception as e:  # noqa: BLE001 — same defensive style as ocr.py
        error_code = "AI_ERROR"
        log.exception("dashboard.summary.unhandled", err=str(e))

    latency_ms = int((time.monotonic() - started) * 1000)

    # Persist call log on its own session.
    async with AsyncSessionLocal() as log_session:
        try:
            log_session.add(
                AICallLog(
                    organization_id=organization_id,
                    user_id=user_id,
                    feature=AIFeature.DASHBOARD_SUMMARY,
                    provider="anthropic",
                    model=model,
                    endpoint="/api/dashboard/overview",
                    prompt_version=prompt.version,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_usd=_calc_cost_usd(model, input_tokens, output_tokens),
                    latency_ms=latency_ms,
                    status=status,
                    error_code=error_code,
                    request_id=get_request_id() or None,
                    metadata_=None,
                )
            )
            await log_session.commit()
        except Exception:  # noqa: BLE001
            await log_session.rollback()
            log.exception("dashboard.summary.log_persist_failed")

    return payload, status, error_code


async def _persist_summary(
    *,
    organization_id: int,
    payload: AISummaryPayload,
) -> None:
    """Cache the digest body + a meta record for staleness display."""
    body = payload.model_dump_json()
    meta = json.dumps(
        {
            "generated_at": _utc_now_naive().isoformat(),
            "error_code": None,
        }
    )
    await redis_cache.set(_summary_key(organization_id), body, ex=_SUMMARY_TTL_SECONDS * 4)
    await redis_cache.set(_summary_meta_key(organization_id), meta, ex=_SUMMARY_TTL_SECONDS * 4)


async def _load_summary_envelope(
    session: AsyncSession,
    *,
    organization_id: int,
    available: bool,
) -> AISummaryEnvelope:
    """Fetch the cached digest and decorate with freshness metadata."""
    body_raw, meta_raw = await asyncio.gather(
        redis_cache.get(_summary_key(organization_id)),
        redis_cache.get(_summary_meta_key(organization_id)),
    )
    if not body_raw:
        return AISummaryEnvelope(
            available=available,
            payload=None,
            is_stale=True,
            staleness_seconds=0,
            generated_at=None,
            error_code="NEVER_GENERATED" if available else "AI_DISABLED",
        )
    try:
        payload = AISummaryPayload.model_validate_json(body_raw)
    except Exception:  # noqa: BLE001 — corrupt cache shouldn't crash the dashboard
        return AISummaryEnvelope(
            available=available,
            payload=None,
            is_stale=True,
            staleness_seconds=0,
            error_code="CACHE_CORRUPTED",
        )
    generated_at: Optional[datetime] = None
    if meta_raw:
        try:
            meta = json.loads(meta_raw)
            generated_at = datetime.fromisoformat(meta["generated_at"])
        except Exception:  # noqa: BLE001
            generated_at = None

    staleness_seconds = 0
    is_stale = False
    if generated_at is not None:
        staleness_seconds = max(
            0, int((_utc_now_naive() - generated_at).total_seconds())
        )
        is_stale = staleness_seconds > _SUMMARY_TTL_SECONDS
    return AISummaryEnvelope(
        available=available,
        payload=payload,
        is_stale=is_stale,
        staleness_seconds=staleness_seconds,
        generated_at=generated_at,
        error_code=None,
    )


async def _maybe_kick_background_refresh(
    *,
    organization_id: int,
    envelope: AISummaryEnvelope,
) -> None:
    """Fire-and-forget regenerate when the cached body is missing or stale.

    Uses a process-local set to dedupe concurrent triggers within one worker
    process. Multi-worker deployments rely on the 30-min Redis TTL plus the
    fact that a duplicate generation just costs one extra call.
    """
    if not envelope.available:
        return
    if envelope.payload is not None and not envelope.is_stale:
        return
    if organization_id in _in_flight_summary_tasks:
        return

    _in_flight_summary_tasks.add(organization_id)

    async def _runner() -> None:
        try:
            payload, status, _ = await _generate_ai_summary(
                organization_id=organization_id
            )
            if status == AICallStatus.SUCCESS and payload is not None:
                await _persist_summary(
                    organization_id=organization_id, payload=payload
                )
        finally:
            _in_flight_summary_tasks.discard(organization_id)

    asyncio.create_task(_runner())


async def refresh_summary_now(
    session: AsyncSession,
    *,
    organization_id: int,
    user_id: Optional[int] = None,
) -> AISummaryEnvelope:
    """Admin-triggered synchronous regeneration (used by /summary/refresh)."""
    if not await AIFeatureGate.is_enabled(
        session, AIFeature.DASHBOARD_SUMMARY, organization_id
    ):
        return await _load_summary_envelope(
            session, organization_id=organization_id, available=False
        )

    payload, status, error_code = await _generate_ai_summary(
        organization_id=organization_id, user_id=user_id
    )
    if status == AICallStatus.SUCCESS and payload is not None:
        await _persist_summary(organization_id=organization_id, payload=payload)
        return AISummaryEnvelope(
            available=True,
            payload=payload,
            is_stale=False,
            staleness_seconds=0,
            generated_at=_utc_now_naive(),
            error_code=None,
        )

    # Fall back to whatever we had cached (may be stale or empty).
    fallback = await _load_summary_envelope(
        session, organization_id=organization_id, available=True
    )
    if fallback.payload is None:
        fallback.error_code = error_code or "AI_ERROR"
    else:
        fallback.error_code = error_code or "AI_ERROR"
        fallback.is_stale = True
    return fallback


# ── Cache get/set wrappers ────────────────────────────────────────────────────


async def _cache_get_json(key: str) -> Optional[Any]:
    raw = await redis_cache.get(key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def _cache_set_json(key: str, value: Any, ttl: int) -> None:
    await redis_cache.set(key, json.dumps(value, default=str), ex=ttl)


# ── Combined overview (entry point used by the router) ────────────────────────


async def get_overview(
    session: AsyncSession,
    *,
    organization_id: int,
) -> DashboardOverviewResponse:
    """Single-call homepage payload — KPIs + trends + AI summary envelope.

    KPIs and trends are cached for 5 minutes. AI summary uses the lazy path
    described in the module docstring.
    """
    cache_hit = True

    # KPIs
    cached_kpi = await _cache_get_json(_kpi_key(organization_id))
    if cached_kpi is not None:
        kpis = DashboardKPIs.model_validate(cached_kpi)
    else:
        cache_hit = False
        kpis = await get_kpi_overview(session, organization_id=organization_id)
        await _cache_set_json(
            _kpi_key(organization_id),
            json.loads(kpis.model_dump_json()),
            _KPI_TTL_SECONDS,
        )

    # Trends
    cached_trends = await _cache_get_json(_trends_key(organization_id))
    if cached_trends is not None:
        trends = DashboardTrends.model_validate(cached_trends)
    else:
        cache_hit = False
        trends = await get_dashboard_trends(
            session, organization_id=organization_id
        )
        await _cache_set_json(
            _trends_key(organization_id),
            json.loads(trends.model_dump_json()),
            _TRENDS_TTL_SECONDS,
        )

    # AI summary — lazy
    available = await AIFeatureGate.is_enabled(
        session, AIFeature.DASHBOARD_SUMMARY, organization_id
    )
    envelope = await _load_summary_envelope(
        session, organization_id=organization_id, available=available
    )
    await _maybe_kick_background_refresh(
        organization_id=organization_id, envelope=envelope
    )

    return DashboardOverviewResponse(
        kpis=kpis,
        summary=envelope,
        trends=trends,
        cache_hit=cache_hit,
        refreshed_at=_utc_now_naive(),
    )


# ── Cache invalidation entry point used by event handlers ─────────────────────


async def invalidate_caches(organization_id: int) -> None:
    """Drop kpi + trends caches; leave AI summary alone (TTL self-manages)."""
    await redis_cache.delete(
        _kpi_key(organization_id),
        _trends_key(organization_id),
    )
