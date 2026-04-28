"""
Unit tests for SalesOrder state machine transitions (Window 10).

Tests:
  1. confirm_so: DRAFT → CONFIRMED (calls apply_reserve per line)
  2. confirm_so: non-DRAFT → InvalidStatusTransitionError
  3. confirm_so: empty lines → BusinessRuleError
  4. cancel_so: DRAFT → CANCELLED (any role, no unreserve)
  5. cancel_so: CONFIRMED → CANCELLED (Manager allowed, calls apply_unreserve)
  6. cancel_so: CONFIRMED → CANCELLED (Sales denied)
  7. cancel_so: PARTIAL_SHIPPED → InvalidStatusTransitionError
  8. cancel_so: FULLY_SHIPPED → InvalidStatusTransitionError
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import (
    AuthorizationError,
    BusinessRuleError,
    InvalidStatusTransitionError,
)
from app.enums import RoleCode, SOStatus
from app.schemas.sales_order import SalesOrderCancel
from app.services import sales as sales_service
from tests.conftest import make_mock_session, make_mock_user


def _make_line(qty_ordered: Decimal = Decimal("5"), qty_shipped: Decimal = Decimal("0")) -> MagicMock:
    line = MagicMock()
    line.id = 100
    line.sku_id = 10
    line.qty_ordered = qty_ordered
    line.qty_shipped = qty_shipped
    line.unit_price_excl_tax = Decimal("50.00")
    return line


def _make_so(status: SOStatus, lines: int = 1, line_qty: Decimal = Decimal("5")) -> MagicMock:
    so = MagicMock()
    so.id = 1
    so.organization_id = 1
    so.document_no = "SO-2026-00001"
    so.status = status
    so.warehouse_id = 1
    so.lines = [_make_line(qty_ordered=line_qty) for _ in range(lines)]
    so.updated_by = None
    so.confirmed_at = None
    so.fully_shipped_at = None
    so.cancelled_at = None
    so.cancel_reason = None
    return so


def _make_repo(so: MagicMock) -> MagicMock:
    repo = MagicMock()
    repo.get_detail = AsyncMock(return_value=so)
    return repo


@pytest.mark.asyncio
async def test_confirm_draft_so_succeeds():
    """DRAFT → CONFIRMED reserves stock per line."""
    session = make_mock_session()
    so = _make_so(SOStatus.DRAFT, lines=2)
    user = make_mock_user(role=RoleCode.SALES)

    with (
        patch(
            "app.services.sales.SalesOrderRepository",
            return_value=_make_repo(so),
        ),
        patch(
            "app.services.sales.inventory_svc.apply_reserve",
            new_callable=AsyncMock,
        ) as reserve_mock,
        patch("app.services.sales.event_bus.publish", new_callable=AsyncMock),
        patch("app.services.sales._to_response", return_value=MagicMock()),
    ):
        await sales_service.confirm_so(session, 1, org_id=1, user=user)

    assert so.status == SOStatus.CONFIRMED
    assert so.confirmed_at is not None
    # apply_reserve called once per line.
    assert reserve_mock.await_count == 2


@pytest.mark.asyncio
async def test_confirm_already_confirmed_raises():
    """Cannot confirm a non-DRAFT SO."""
    session = make_mock_session()
    so = _make_so(SOStatus.CONFIRMED)
    user = make_mock_user()

    with patch(
        "app.services.sales.SalesOrderRepository",
        return_value=_make_repo(so),
    ):
        with pytest.raises(InvalidStatusTransitionError):
            await sales_service.confirm_so(session, 1, org_id=1, user=user)


@pytest.mark.asyncio
async def test_confirm_empty_lines_raises():
    """Cannot confirm an SO with no lines."""
    session = make_mock_session()
    so = _make_so(SOStatus.DRAFT, lines=0)
    user = make_mock_user(role=RoleCode.SALES)

    with patch(
        "app.services.sales.SalesOrderRepository",
        return_value=_make_repo(so),
    ):
        with pytest.raises(BusinessRuleError) as exc_info:
            await sales_service.confirm_so(session, 1, org_id=1, user=user)
    assert exc_info.value.error_code == "SO_NO_LINES"


@pytest.mark.asyncio
async def test_cancel_draft_so_any_role():
    """DRAFT SO can be cancelled by Sales without unreserve."""
    session = make_mock_session()
    so = _make_so(SOStatus.DRAFT)
    user = make_mock_user(role=RoleCode.SALES)
    data = SalesOrderCancel(cancel_reason="Customer changed mind")

    with (
        patch(
            "app.services.sales.SalesOrderRepository",
            return_value=_make_repo(so),
        ),
        patch(
            "app.services.sales.inventory_svc.apply_unreserve",
            new_callable=AsyncMock,
        ) as unreserve_mock,
        patch("app.services.sales.event_bus.publish", new_callable=AsyncMock),
        patch("app.services.sales._to_response", return_value=MagicMock()),
    ):
        await sales_service.cancel_so(session, 1, data, org_id=1, user=user)

    assert so.status == SOStatus.CANCELLED
    # No unreserve for DRAFT (nothing was reserved yet).
    unreserve_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_cancel_confirmed_so_manager_releases_reserved():
    """CONFIRMED SO cancelled by Manager unreserves remaining quantity."""
    session = make_mock_session()
    so = _make_so(SOStatus.CONFIRMED, lines=2, line_qty=Decimal("10"))
    user = make_mock_user(role=RoleCode.MANAGER)
    data = SalesOrderCancel(cancel_reason="Customer cancelled")

    with (
        patch(
            "app.services.sales.SalesOrderRepository",
            return_value=_make_repo(so),
        ),
        patch(
            "app.services.sales.inventory_svc.apply_unreserve",
            new_callable=AsyncMock,
        ) as unreserve_mock,
        patch("app.services.sales.event_bus.publish", new_callable=AsyncMock),
        patch("app.services.sales._to_response", return_value=MagicMock()),
    ):
        await sales_service.cancel_so(session, 1, data, org_id=1, user=user)

    assert so.status == SOStatus.CANCELLED
    # Two lines, each fully unreserved (qty_shipped=0 → release all qty_ordered).
    assert unreserve_mock.await_count == 2
    # Each call should request the full ordered quantity.
    for call in unreserve_mock.await_args_list:
        assert call.kwargs["qty"] == Decimal("10")


@pytest.mark.asyncio
async def test_cancel_confirmed_so_sales_denied():
    """Sales role cannot cancel a CONFIRMED SO (only Manager/Admin)."""
    session = make_mock_session()
    so = _make_so(SOStatus.CONFIRMED)
    user = make_mock_user(role=RoleCode.SALES)
    data = SalesOrderCancel(cancel_reason="Test")

    with patch(
        "app.services.sales.SalesOrderRepository",
        return_value=_make_repo(so),
    ):
        with pytest.raises(AuthorizationError):
            await sales_service.cancel_so(session, 1, data, org_id=1, user=user)


@pytest.mark.asyncio
async def test_cancel_partial_shipped_raises():
    """PARTIAL_SHIPPED SO cannot be cancelled (must use Credit Note)."""
    session = make_mock_session()
    so = _make_so(SOStatus.PARTIAL_SHIPPED)
    user = make_mock_user(role=RoleCode.ADMIN)
    data = SalesOrderCancel(cancel_reason="Test")

    with patch(
        "app.services.sales.SalesOrderRepository",
        return_value=_make_repo(so),
    ):
        with pytest.raises(InvalidStatusTransitionError):
            await sales_service.cancel_so(session, 1, data, org_id=1, user=user)


@pytest.mark.asyncio
async def test_cancel_fully_shipped_raises():
    """FULLY_SHIPPED SO cannot be cancelled."""
    session = make_mock_session()
    so = _make_so(SOStatus.FULLY_SHIPPED)
    user = make_mock_user(role=RoleCode.ADMIN)
    data = SalesOrderCancel(cancel_reason="Test")

    with patch(
        "app.services.sales.SalesOrderRepository",
        return_value=_make_repo(so),
    ):
        with pytest.raises(InvalidStatusTransitionError):
            await sales_service.cancel_so(session, 1, data, org_id=1, user=user)
