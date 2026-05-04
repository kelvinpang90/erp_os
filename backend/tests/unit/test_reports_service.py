"""Unit tests for the W15 reports service.

These exercise the post-aggregation logic — zero-filling, share %, turnover
ratio guards — by feeding fabricated SQL row tuples through patched
``session.execute`` calls. They do not validate the SQL itself; the
end-to-end docker run plus the existing integration tests cover that.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import reports as reports_service


def _result(rows: list[tuple]):
    res = MagicMock()
    res.all = MagicMock(return_value=rows)
    return res


def _session_with_results(*results) -> AsyncMock:
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=list(results))
    return session


@pytest.mark.asyncio
class TestSalesTrend:
    async def test_zero_fills_missing_days(self) -> None:
        today = date.today()
        rows = [(today - timedelta(days=2), Decimal("100"))]
        session = _session_with_results(_result(rows))

        out = await reports_service.get_sales_trend(
            session, organization_id=1, days=5
        )

        assert len(out.points) == 5
        assert out.total == Decimal("100")
        # All non-matching dates should be zero
        nonzero_buckets = [p.bucket for p in out.points if p.value > 0]
        assert nonzero_buckets == [today - timedelta(days=2)]


@pytest.mark.asyncio
class TestPurchaseTrend:
    async def test_aggregates_total(self) -> None:
        today = date.today()
        rows = [
            (today, Decimal("50")),
            (today - timedelta(days=1), Decimal("25")),
        ]
        session = _session_with_results(_result(rows))

        out = await reports_service.get_purchase_trend(
            session, organization_id=1, days=7
        )
        assert out.total == Decimal("75")
        assert out.days == 7


@pytest.mark.asyncio
class TestTopSkus:
    async def test_maps_rows_to_response(self) -> None:
        rows = [
            (10, "SKU-A", "Widget", "小部件", Decimal("100"), Decimal("9999.99")),
            (11, "SKU-B", "Gadget", None, Decimal("50"), Decimal("4444.44")),
        ]
        session = _session_with_results(_result(rows))

        out = await reports_service.get_top_skus_by_sales(
            session, organization_id=1, days=30, limit=5
        )

        assert len(out.rows) == 2
        assert out.rows[0].code == "SKU-A"
        assert out.rows[0].amount == Decimal("9999.99")
        assert out.rows[1].name_zh is None


@pytest.mark.asyncio
class TestCategoryShare:
    async def test_share_percentages_sum_to_100(self) -> None:
        rows = [
            (1, "Beverages", Decimal("600")),
            (2, "Snacks", Decimal("400")),
        ]
        session = _session_with_results(_result(rows))

        out = await reports_service.get_category_sales_share(
            session, organization_id=1, days=30
        )

        assert out.total == Decimal("1000")
        assert sum((r.share_pct for r in out.rows), Decimal("0")) == Decimal("100.00")
        assert out.rows[0].share_pct == Decimal("60.00")

    async def test_handles_uncategorized_and_zero_total(self) -> None:
        rows = [(None, None, Decimal("0"))]
        session = _session_with_results(_result(rows))

        out = await reports_service.get_category_sales_share(
            session, organization_id=1, days=30
        )

        assert out.total == Decimal("0")
        assert out.rows[0].category_name == "Uncategorized"
        assert out.rows[0].share_pct == Decimal("0")


@pytest.mark.asyncio
class TestInventoryTurnover:
    async def test_ratio_zero_when_no_inventory_value(self) -> None:
        cogs_rows = [(10, "SKU-A", "Widget", Decimal("500"))]
        inv_rows: list[tuple] = []  # no inventory snapshot for this sku
        session = _session_with_results(_result(cogs_rows), _result(inv_rows))

        out = await reports_service.get_inventory_turnover(
            session, organization_id=1, days=30, limit=10
        )

        assert len(out.rows) == 1
        assert out.rows[0].cogs == Decimal("500")
        assert out.rows[0].avg_inventory_value == Decimal("0")
        assert out.rows[0].turnover_ratio == Decimal("0")

    async def test_ratio_computed_when_inventory_present(self) -> None:
        cogs_rows = [(10, "SKU-A", "Widget", Decimal("1000"))]
        inv_rows = [(10, Decimal("250"))]
        session = _session_with_results(_result(cogs_rows), _result(inv_rows))

        out = await reports_service.get_inventory_turnover(
            session, organization_id=1, days=30, limit=10
        )

        assert out.rows[0].turnover_ratio == Decimal("4.00")

    async def test_empty_when_no_cogs(self) -> None:
        session = _session_with_results(_result([]))

        out = await reports_service.get_inventory_turnover(
            session, organization_id=1, days=30
        )

        assert out.rows == []


@pytest.mark.asyncio
class TestEInvoiceDistribution:
    async def test_total_is_sum_of_buckets(self) -> None:
        from app.enums import InvoiceStatus

        rows = [
            (InvoiceStatus.DRAFT, 5),
            (InvoiceStatus.VALIDATED, 12),
        ]
        session = _session_with_results(_result(rows))

        out = await reports_service.get_einvoice_status_distribution(
            session, organization_id=1, days=None
        )

        assert out.total == 17
        assert {r.status for r in out.rows} == {"DRAFT", "VALIDATED"}


@pytest.mark.asyncio
class TestAICostMetrics:
    async def test_aggregates_daily_and_per_feature(self) -> None:
        from app.enums import AIFeature

        today = date.today()
        daily_rows = [(today, Decimal("0.05"))]
        feature_rows = [
            (AIFeature.OCR_INVOICE, 10, Decimal("0.04")),
            (AIFeature.DASHBOARD_SUMMARY, 5, Decimal("0.01")),
        ]
        session = _session_with_results(_result(daily_rows), _result(feature_rows))

        out = await reports_service.get_ai_cost_metrics(
            session, organization_id=1, days=7
        )

        assert out.total_calls == 15
        assert out.total_cost_usd == Decimal("0.05")
        assert len(out.series) == 7
        assert {r.feature for r in out.by_feature} == {
            "OCR_INVOICE",
            "DASHBOARD_SUMMARY",
        }


@pytest.mark.asyncio
class TestWarehouseStockDistribution:
    async def test_sums_total_and_orders_rows(self) -> None:
        rows = [
            (1, "WH-KL", "Kuala Lumpur", Decimal("15000"), 30),
            (2, "WH-PG", "Penang", Decimal("8500"), 18),
        ]
        session = _session_with_results(_result(rows))

        out = await reports_service.get_warehouse_stock_distribution(
            session, organization_id=1
        )

        assert out.total_value == Decimal("23500")
        assert out.rows[0].warehouse_code == "WH-KL"
        assert out.rows[0].sku_count == 30
