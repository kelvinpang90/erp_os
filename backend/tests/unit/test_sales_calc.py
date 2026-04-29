"""Unit tests for sales `_calc_line` + `_load_tax_rate_map` (the
server-authoritative tax rate path).

Bug under test (2026-04-29): the frontend used to send a stale
`tax_rate_percent` after the user changed `tax_rate_id` in the row form.
Backend now ignores client `tax_rate_percent` and reads the rate from the
``tax_rates`` table, so a wrong client value can't poison stored data.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import ValidationError
from app.schemas.sales_order import SOLineCreate
from app.services import sales as sales_svc


# ── _calc_line ─────────────────────────────────────────────────────────────


def _make_line(
    *,
    qty: Decimal = Decimal("10"),
    price: Decimal = Decimal("100"),
    tax_rate_id: int = 1,
    tax_rate_percent: Decimal = Decimal("0"),
    discount_percent: Decimal = Decimal("0"),
) -> SOLineCreate:
    return SOLineCreate(
        sku_id=1,
        uom_id=1,
        qty_ordered=qty,
        unit_price_excl_tax=price,
        tax_rate_id=tax_rate_id,
        tax_rate_percent=tax_rate_percent,
        discount_percent=discount_percent,
    )


def test_calc_line_uses_authoritative_percent_not_input():
    """Even if line_in.tax_rate_percent says 99, the result follows the
    explicit ``tax_rate_percent=`` keyword argument (the DB-loaded value).
    """
    line_in = _make_line(tax_rate_percent=Decimal("99"))
    out = sales_svc._calc_line(line_in, 1, tax_rate_percent=Decimal("6"))

    # 10 * 100 = 1000 excl tax, 6% tax = 60
    assert out["tax_rate_percent"] == Decimal("6.00")
    assert out["tax_amount"] == Decimal("60.00")
    assert out["line_total_excl_tax"] == Decimal("1000.00")
    assert out["line_total_incl_tax"] == Decimal("1060.00")


def test_calc_line_zero_rate_zero_tax():
    line_in = _make_line()
    out = sales_svc._calc_line(line_in, 1, tax_rate_percent=Decimal("0"))
    assert out["tax_amount"] == Decimal("0.00")
    assert out["line_total_incl_tax"] == Decimal("1000.00")


def test_calc_line_with_discount():
    line_in = _make_line(discount_percent=Decimal("10"))
    # gross 1000, disc 100, excl 900, tax 6% of 900 = 54, incl 954
    out = sales_svc._calc_line(line_in, 1, tax_rate_percent=Decimal("6"))
    assert out["discount_amount"] == Decimal("100.00")
    assert out["line_total_excl_tax"] == Decimal("900.00")
    assert out["tax_amount"] == Decimal("54.00")
    assert out["line_total_incl_tax"] == Decimal("954.00")


# ── _load_tax_rate_map ─────────────────────────────────────────────────────


def _make_db_rows(rates: dict[int, Decimal]) -> MagicMock:
    """Build a mock for `(await session.execute(stmt)).all()` returning rows
    with .id and .rate attributes.
    """
    result = MagicMock()
    result.all = MagicMock(
        return_value=[MagicMock(id=i, rate=r) for i, r in rates.items()]
    )
    return result


@pytest.mark.asyncio
async def test_load_tax_rate_map_happy_path():
    session = AsyncMock()
    session.execute = AsyncMock(
        return_value=_make_db_rows({1: Decimal("6.00"), 2: Decimal("0.00")})
    )

    rate_map = await sales_svc._load_tax_rate_map(session, org_id=1, ids={1, 2})

    assert rate_map == {1: Decimal("6.00"), 2: Decimal("0.00")}
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_load_tax_rate_map_missing_id_raises():
    session = AsyncMock()
    # Only id=1 returned; id=99 missing (cross-org / inactive / non-existent).
    session.execute = AsyncMock(
        return_value=_make_db_rows({1: Decimal("6.00")})
    )

    with pytest.raises(ValidationError) as exc:
        await sales_svc._load_tax_rate_map(session, org_id=1, ids={1, 99})

    assert exc.value.error_code == "TAX_RATE_INVALID"
    assert "99" in exc.value.message


@pytest.mark.asyncio
async def test_load_tax_rate_map_empty_ids_no_query():
    """No ids → returns empty dict without hitting the DB."""
    session = AsyncMock()
    session.execute = AsyncMock()

    rate_map = await sales_svc._load_tax_rate_map(session, org_id=1, ids=set())

    assert rate_map == {}
    session.execute.assert_not_awaited()
