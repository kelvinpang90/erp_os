"""Unit tests for purchase `_calc_line` + `_load_tax_rate_map`. Mirrors
``test_sales_calc.py`` for the PO side (same bug pattern, same fix).
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import ValidationError
from app.schemas.purchase_order import POLineCreate
from app.services import purchase as purchase_svc


def _make_line(
    *,
    qty: Decimal = Decimal("10"),
    price: Decimal = Decimal("100"),
    tax_rate_id: int = 1,
    tax_rate_percent: Decimal = Decimal("0"),
    discount_percent: Decimal = Decimal("0"),
) -> POLineCreate:
    return POLineCreate(
        sku_id=1,
        uom_id=1,
        qty_ordered=qty,
        unit_price_excl_tax=price,
        tax_rate_id=tax_rate_id,
        tax_rate_percent=tax_rate_percent,
        discount_percent=discount_percent,
    )


def test_calc_line_uses_authoritative_percent_not_input():
    line_in = _make_line(tax_rate_percent=Decimal("99"))
    out = purchase_svc._calc_line(line_in, 1, tax_rate_percent=Decimal("6"))

    assert out["tax_rate_percent"] == Decimal("6.00")
    assert out["tax_amount"] == Decimal("60.00")
    assert out["line_total_incl_tax"] == Decimal("1060.00")


def test_calc_line_zero_rate_zero_tax():
    line_in = _make_line()
    out = purchase_svc._calc_line(line_in, 1, tax_rate_percent=Decimal("0"))
    assert out["tax_amount"] == Decimal("0.00")
    assert out["line_total_incl_tax"] == Decimal("1000.00")


def test_calc_line_with_discount():
    line_in = _make_line(discount_percent=Decimal("10"))
    out = purchase_svc._calc_line(line_in, 1, tax_rate_percent=Decimal("6"))
    assert out["discount_amount"] == Decimal("100.00")
    assert out["line_total_excl_tax"] == Decimal("900.00")
    assert out["tax_amount"] == Decimal("54.00")
    assert out["line_total_incl_tax"] == Decimal("954.00")


def _make_db_rows(rates: dict[int, Decimal]) -> MagicMock:
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

    rate_map = await purchase_svc._load_tax_rate_map(session, org_id=1, ids={1, 2})

    assert rate_map == {1: Decimal("6.00"), 2: Decimal("0.00")}


@pytest.mark.asyncio
async def test_load_tax_rate_map_missing_id_raises():
    session = AsyncMock()
    session.execute = AsyncMock(
        return_value=_make_db_rows({1: Decimal("6.00")})
    )

    with pytest.raises(ValidationError) as exc:
        await purchase_svc._load_tax_rate_map(session, org_id=1, ids={1, 99})

    assert exc.value.error_code == "TAX_RATE_INVALID"
    assert "99" in exc.value.message


@pytest.mark.asyncio
async def test_load_tax_rate_map_empty_ids_no_query():
    session = AsyncMock()
    session.execute = AsyncMock()

    rate_map = await purchase_svc._load_tax_rate_map(session, org_id=1, ids=set())

    assert rate_map == {}
    session.execute.assert_not_awaited()
