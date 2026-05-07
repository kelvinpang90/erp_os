"""Unit tests for the W15 dashboard service.

Focus areas:
* KPI computation builds the right SQL paths and tolerates empty data.
* /overview cache hit short-circuits the DB; cache miss persists the result.
* AI summary degrades gracefully (gate disabled / timeout / parse error).
* Cache invalidation entry point clears the right Redis keys.
"""

from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.enums import AICallStatus
from app.schemas.dashboard import (
    AISummaryContent,
    AISummaryEnvelope,
    AISummaryPayload,
    DashboardKPIs,
    DashboardTrends,
    StatusBucket,
    TrendPoint,
)


def _bilingual(headline_en: str, finding_en: str, action_en: str) -> AISummaryPayload:
    """Helper to build a bilingual AISummaryPayload for tests."""
    return AISummaryPayload(
        en=AISummaryContent(
            headline=headline_en,
            key_findings=[finding_en],
            action_items=[action_en],
        ),
        zh=AISummaryContent(
            headline=f"{headline_en}（中）",
            key_findings=[f"{finding_en}（中）"],
            action_items=[f"{action_en}（中）"],
        ),
    )
from app.services import dashboard as dashboard_service


def _scalar_one_result(value):
    """Build an execute() result whose .scalar_one() returns ``value``."""
    result = MagicMock()
    result.scalar_one = MagicMock(return_value=value)
    return result


def _make_session(*scalar_one_values) -> AsyncMock:
    """Mock session whose successive execute() calls return given scalars."""
    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[_scalar_one_result(v) for v in scalar_one_values]
    )
    return session


@pytest.mark.asyncio
class TestKPIOverview:
    async def test_returns_zero_when_no_data(self) -> None:
        # Six successive scalar_one() calls — see service for ordering.
        session = _make_session(0, 0, 0, 0, 0, 0)
        kpis = await dashboard_service.get_kpi_overview(session, organization_id=1)

        assert kpis.today_sales == Decimal("0")
        assert kpis.today_purchases == Decimal("0")
        assert kpis.pending_shipments == 0
        assert kpis.low_stock_count == 0
        assert kpis.pending_einvoices == 0
        assert kpis.ai_cost_today_usd == Decimal("0")

    async def test_returns_real_numbers(self) -> None:
        session = _make_session(
            Decimal("1234.56"),  # today_sales
            Decimal("987.65"),   # today_purchases
            5,                    # pending_shipments
            3,                    # low_stock_count
            2,                    # pending_einvoices
            Decimal("0.0421"),   # ai_cost_today_usd
        )
        kpis = await dashboard_service.get_kpi_overview(session, organization_id=1)

        assert kpis.today_sales == Decimal("1234.56")
        assert kpis.pending_shipments == 5
        assert kpis.low_stock_count == 3
        assert kpis.ai_cost_today_usd == Decimal("0.0421").quantize(Decimal("0.000001"))


@pytest.mark.asyncio
class TestOverviewCache:
    """The combined /overview endpoint should hit Redis first."""

    @pytest.fixture
    def fake_kpi_payload(self) -> dict:
        kpis = DashboardKPIs(
            today_sales=Decimal("100"),
            today_purchases=Decimal("50"),
            pending_shipments=1,
            low_stock_count=2,
            pending_einvoices=3,
            ai_cost_today_usd=Decimal("0.001"),
        )
        return json.loads(kpis.model_dump_json())

    @pytest.fixture
    def fake_trends_payload(self) -> dict:
        trends = DashboardTrends(
            sales_last_30d=[],
            purchase_last_30d=[],
            einvoice_status_distribution=[StatusBucket(status="DRAFT", count=1)],
            ai_cost_last_30d=[],
        )
        return json.loads(trends.model_dump_json())

    async def test_cache_hit_skips_db_queries(
        self, fake_kpi_payload, fake_trends_payload
    ) -> None:
        cached_summary = AISummaryEnvelope(
            available=False, payload=None, error_code="AI_DISABLED"
        )

        async def fake_get_json(key):
            if key.endswith(":kpi"):
                return fake_kpi_payload
            if key.endswith(":trends"):
                return fake_trends_payload
            return None

        # No DB execute — the session shouldn't even be touched.
        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=AssertionError("DB should not be hit on cache hit")
        )

        with patch.object(
            dashboard_service, "_cache_get_json", new=AsyncMock(side_effect=fake_get_json)
        ), patch.object(
            dashboard_service,
            "_load_summary_envelope",
            new=AsyncMock(return_value=cached_summary),
        ), patch.object(
            dashboard_service,
            "_maybe_kick_background_refresh",
            new=AsyncMock(),
        ), patch.object(
            dashboard_service.AIFeatureGate,
            "is_enabled",
            new=AsyncMock(return_value=False),
        ):
            result = await dashboard_service.get_overview(session, organization_id=7)

        assert result.cache_hit is True
        assert result.kpis.today_sales == Decimal("100")
        assert result.summary.available is False

    async def test_cache_miss_runs_queries_and_persists(
        self, fake_kpi_payload, fake_trends_payload
    ) -> None:
        # Session feeds 6 KPI scalars + 4 trends queries (sales, purchase,
        # einvoice dist, ai cost). Reports module wraps each, so we patch the
        # reports calls instead of mocking the underlying SQL paths.
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[_scalar_one_result(0)] * 6)

        async def fake_get_json(_key):
            return None

        cached_summary = AISummaryEnvelope(available=False, error_code="AI_DISABLED")

        from app.schemas.dashboard import (
            AICostMetricsResponse,
            EInvoiceStatusDistributionResponse,
            TrendSeriesResponse,
        )

        empty_trend = TrendSeriesResponse(points=[], total=Decimal("0"), days=30)
        empty_dist = EInvoiceStatusDistributionResponse(rows=[], total=0)
        empty_cost = AICostMetricsResponse(
            series=[],
            total_cost_usd=Decimal("0"),
            total_calls=0,
            by_feature=[],
            days=30,
        )

        set_calls: list[tuple[str, int]] = []

        async def fake_set_json(key, _value, ttl):
            set_calls.append((key, ttl))

        with patch.object(
            dashboard_service, "_cache_get_json", new=AsyncMock(side_effect=fake_get_json)
        ), patch.object(
            dashboard_service, "_cache_set_json", new=AsyncMock(side_effect=fake_set_json)
        ), patch.object(
            dashboard_service.reports_service,
            "get_sales_trend",
            new=AsyncMock(return_value=empty_trend),
        ), patch.object(
            dashboard_service.reports_service,
            "get_purchase_trend",
            new=AsyncMock(return_value=empty_trend),
        ), patch.object(
            dashboard_service.reports_service,
            "get_einvoice_status_distribution",
            new=AsyncMock(return_value=empty_dist),
        ), patch.object(
            dashboard_service.reports_service,
            "get_ai_cost_metrics",
            new=AsyncMock(return_value=empty_cost),
        ), patch.object(
            dashboard_service,
            "_load_summary_envelope",
            new=AsyncMock(return_value=cached_summary),
        ), patch.object(
            dashboard_service,
            "_maybe_kick_background_refresh",
            new=AsyncMock(),
        ), patch.object(
            dashboard_service.AIFeatureGate,
            "is_enabled",
            new=AsyncMock(return_value=False),
        ):
            result = await dashboard_service.get_overview(session, organization_id=9)

        assert result.cache_hit is False
        # Both KPI and trends should have been written back.
        keys_written = {k for k, _ in set_calls}
        assert "dashboard:9:kpi" in keys_written
        assert "dashboard:9:trends" in keys_written


@pytest.mark.asyncio
class TestAISummaryDegradation:
    async def test_gate_disabled_returns_unavailable_envelope(self) -> None:
        session = AsyncMock()
        with patch.object(
            dashboard_service.AIFeatureGate,
            "is_enabled",
            new=AsyncMock(return_value=False),
        ), patch.object(
            dashboard_service, "_generate_ai_summary", new=AsyncMock()
        ) as gen_mock:
            envelope = await dashboard_service.refresh_summary_now(
                session, organization_id=1, user_id=1
            )
            gen_mock.assert_not_called()

        assert envelope.available is False
        assert envelope.payload is None

    async def test_timeout_falls_back_to_cached_body(self) -> None:
        session = AsyncMock()
        cached = AISummaryEnvelope(
            available=True,
            payload=_bilingual("yesterday", "a", "b"),
            staleness_seconds=3600,
            is_stale=True,
            error_code=None,
        )
        with patch.object(
            dashboard_service.AIFeatureGate,
            "is_enabled",
            new=AsyncMock(return_value=True),
        ), patch.object(
            dashboard_service,
            "_generate_ai_summary",
            new=AsyncMock(return_value=(None, AICallStatus.TIMEOUT, "AI_TIMEOUT")),
        ), patch.object(
            dashboard_service,
            "_load_summary_envelope",
            new=AsyncMock(return_value=cached),
        ), patch.object(
            dashboard_service,
            "_persist_summary",
            new=AsyncMock(),
        ):
            envelope = await dashboard_service.refresh_summary_now(
                session, organization_id=1, user_id=1
            )

        assert envelope.payload is not None
        assert envelope.payload.en.headline == "yesterday"
        assert envelope.payload.zh.headline == "yesterday（中）"
        assert envelope.error_code == "AI_TIMEOUT"
        assert envelope.is_stale is True

    async def test_success_persists_and_returns_fresh_envelope(self) -> None:
        session = AsyncMock()
        new_payload = _bilingual("today is good", "sales up", "nothing urgent")

        persist_mock = AsyncMock()
        with patch.object(
            dashboard_service.AIFeatureGate,
            "is_enabled",
            new=AsyncMock(return_value=True),
        ), patch.object(
            dashboard_service,
            "_generate_ai_summary",
            new=AsyncMock(return_value=(new_payload, AICallStatus.SUCCESS, None)),
        ), patch.object(
            dashboard_service,
            "_persist_summary",
            new=persist_mock,
        ):
            envelope = await dashboard_service.refresh_summary_now(
                session, organization_id=1, user_id=1
            )

        assert envelope.available is True
        assert envelope.payload == new_payload
        assert envelope.is_stale is False
        assert envelope.staleness_seconds == 0
        persist_mock.assert_called_once()


@pytest.mark.asyncio
class TestInvalidateCaches:
    async def test_deletes_kpi_and_trends_keys(self) -> None:
        delete_mock = AsyncMock()
        with patch.object(dashboard_service.redis_cache, "delete", new=delete_mock):
            await dashboard_service.invalidate_caches(42)

        delete_mock.assert_called_once_with(
            "dashboard:42:kpi", "dashboard:42:trends"
        )
