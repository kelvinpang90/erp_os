"""
Unit tests for the no-oversell guarantee (Window 10).

These tests verify the inventory layer's atomic UPDATE-with-WHERE pattern
correctly prevents committing a confirm_so that would push reserved past
on_hand - quality_hold (i.e. drive available negative).

Tests:
  1. apply_reserve happy path: rowcount=1 → reserved increment + audit row + event
  2. apply_reserve insufficient: rowcount=0 → InsufficientStockError
  3. apply_unreserve happy path: rowcount=1 → reserved decrement
  4. apply_unreserve underflow: rowcount=0 → BusinessRuleError(UNRESERVE_UNDERFLOW)
  5. apply_sales_out happy path: returns avg_cost snapshot, version-locked update
  6. apply_sales_out conflict: rowcount=0 → BusinessRuleError(STOCK_CONFLICT)
  7. confirm_so rolls back when apply_reserve raises (concurrent grab the last unit)
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import (
    BusinessRuleError,
    InsufficientStockError,
)
from app.enums import RoleCode, SOStatus, StockMovementSourceType, StockMovementType
from app.services import inventory as inventory_svc
from app.services import sales as sales_service
from tests.conftest import make_mock_session, make_mock_user


def _make_stock(
    *,
    on_hand: Decimal = Decimal("100"),
    reserved: Decimal = Decimal("0"),
    quality_hold: Decimal = Decimal("0"),
    avg_cost: Decimal = Decimal("8.0000"),
    version: int = 1,
) -> MagicMock:
    stock = MagicMock()
    stock.id = 999
    stock.organization_id = 1
    stock.sku_id = 11
    stock.warehouse_id = 21
    stock.on_hand = on_hand
    stock.reserved = reserved
    stock.quality_hold = quality_hold
    stock.avg_cost = avg_cost
    stock.version = version
    return stock


# ── apply_reserve ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_apply_reserve_happy_path():
    """available >= qty → reserved increments + StockMovement(RESERVE) audited."""
    stock = _make_stock(on_hand=Decimal("100"), reserved=Decimal("20"))
    session = make_mock_session()

    select_result = MagicMock()
    select_result.scalar_one_or_none = MagicMock(return_value=stock)
    update_result = MagicMock()
    update_result.rowcount = 1
    session.execute = AsyncMock(side_effect=[select_result, update_result])

    with patch.object(inventory_svc.event_bus, "publish", new=AsyncMock()) as pub:
        result = await inventory_svc.apply_reserve(
            session,
            org_id=1,
            sku_id=11,
            warehouse_id=21,
            qty=Decimal("30"),
            source_document_id=555,
            source_line_id=777,
            actor_user_id=42,
        )

    assert result is stock
    # session.add called once for the StockMovement (stock already exists).
    assert session.add.call_count == 1
    movement = session.add.call_args.args[0]
    assert movement.movement_type == StockMovementType.RESERVE
    assert movement.source_document_type == StockMovementSourceType.SO
    assert movement.quantity == Decimal("30")
    pub.assert_awaited_once()


@pytest.mark.asyncio
async def test_apply_reserve_insufficient_raises():
    """available < qty (atomic UPDATE rowcount=0) → InsufficientStockError."""
    stock = _make_stock(on_hand=Decimal("10"), reserved=Decimal("8"))
    session = make_mock_session()

    select_result = MagicMock()
    select_result.scalar_one_or_none = MagicMock(return_value=stock)
    update_result = MagicMock()
    update_result.rowcount = 0  # WHERE clause failed: available < qty
    session.execute = AsyncMock(side_effect=[select_result, update_result])

    with pytest.raises(InsufficientStockError) as exc_info:
        await inventory_svc.apply_reserve(
            session,
            org_id=1,
            sku_id=11,
            warehouse_id=21,
            qty=Decimal("5"),  # available is 10-8=2, requesting 5 → fail
            source_document_id=555,
        )

    assert exc_info.value.error_code == "INSUFFICIENT_STOCK"
    # No StockMovement should be added on failure.
    assert session.add.call_count == 0


@pytest.mark.asyncio
async def test_apply_reserve_invalid_qty():
    """qty <= 0 → ValueError (caught early before DB I/O)."""
    session = make_mock_session()
    with pytest.raises(ValueError):
        await inventory_svc.apply_reserve(
            session,
            org_id=1,
            sku_id=11,
            warehouse_id=21,
            qty=Decimal("0"),
            source_document_id=1,
        )


# ── apply_unreserve ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_apply_unreserve_happy_path():
    """reserved >= qty → decrement + StockMovement(UNRESERVE)."""
    stock = _make_stock(reserved=Decimal("30"))
    session = make_mock_session()

    select_result = MagicMock()
    select_result.scalar_one_or_none = MagicMock(return_value=stock)
    update_result = MagicMock()
    update_result.rowcount = 1
    session.execute = AsyncMock(side_effect=[select_result, update_result])

    with patch.object(inventory_svc.event_bus, "publish", new=AsyncMock()):
        await inventory_svc.apply_unreserve(
            session,
            org_id=1,
            sku_id=11,
            warehouse_id=21,
            qty=Decimal("20"),
            source_document_id=555,
        )

    movement = session.add.call_args.args[0]
    assert movement.movement_type == StockMovementType.UNRESERVE


@pytest.mark.asyncio
async def test_apply_unreserve_underflow_raises():
    """reserved < qty → BusinessRuleError(UNRESERVE_UNDERFLOW)."""
    stock = _make_stock(reserved=Decimal("3"))
    session = make_mock_session()

    select_result = MagicMock()
    select_result.scalar_one_or_none = MagicMock(return_value=stock)
    update_result = MagicMock()
    update_result.rowcount = 0
    session.execute = AsyncMock(side_effect=[select_result, update_result])

    with pytest.raises(BusinessRuleError) as exc_info:
        await inventory_svc.apply_unreserve(
            session,
            org_id=1,
            sku_id=11,
            warehouse_id=21,
            qty=Decimal("10"),
            source_document_id=555,
        )

    assert exc_info.value.error_code == "UNRESERVE_UNDERFLOW"


# ── apply_sales_out ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_apply_sales_out_happy_path_returns_avg_cost():
    """on_hand>=qty AND reserved>=qty → both decrement, snapshot avg_cost returned."""
    stock = _make_stock(
        on_hand=Decimal("100"),
        reserved=Decimal("30"),
        avg_cost=Decimal("12.5000"),
        version=5,
    )
    session = make_mock_session()

    select_result = MagicMock()
    select_result.scalar_one_or_none = MagicMock(return_value=stock)
    update_result = MagicMock()
    update_result.rowcount = 1
    session.execute = AsyncMock(side_effect=[select_result, update_result])

    with patch.object(inventory_svc.event_bus, "publish", new=AsyncMock()):
        result_stock, snapshot = await inventory_svc.apply_sales_out(
            session,
            org_id=1,
            sku_id=11,
            warehouse_id=21,
            qty=Decimal("20"),
            source_document_id=999,
            source_line_id=1001,
            actor_user_id=42,
        )

    assert snapshot == Decimal("12.5000")
    assert result_stock is stock
    movement = session.add.call_args.args[0]
    assert movement.movement_type == StockMovementType.SALES_OUT
    assert movement.source_document_type == StockMovementSourceType.DO
    assert movement.unit_cost == Decimal("12.5000")
    assert movement.avg_cost_after == Decimal("12.5000")  # WAC unchanged on outbound


@pytest.mark.asyncio
async def test_apply_sales_out_conflict_raises():
    """rowcount=0 (concurrent modification or not-enough-reserved) → STOCK_CONFLICT."""
    stock = _make_stock(on_hand=Decimal("100"), reserved=Decimal("30"))
    session = make_mock_session()

    select_result = MagicMock()
    select_result.scalar_one_or_none = MagicMock(return_value=stock)
    update_result = MagicMock()
    update_result.rowcount = 0
    session.execute = AsyncMock(side_effect=[select_result, update_result])

    with patch.object(inventory_svc.event_bus, "publish", new=AsyncMock()):
        with pytest.raises(BusinessRuleError) as exc_info:
            await inventory_svc.apply_sales_out(
                session,
                org_id=1,
                sku_id=11,
                warehouse_id=21,
                qty=Decimal("50"),
                source_document_id=999,
            )

    assert exc_info.value.error_code == "STOCK_CONFLICT"


# ── End-to-end: confirm_so propagates InsufficientStockError ────────────────


@pytest.mark.asyncio
async def test_confirm_so_propagates_insufficient_stock():
    """When apply_reserve raises mid-loop, confirm_so propagates the error.

    The transaction (managed by the FastAPI dependency layer) will roll back,
    so any partial Stock updates from earlier lines are undone. We assert that
    the exception bubbles up, status is NOT advanced, and event_bus.publish
    was never called (no DocumentStatusChanged emitted).
    """
    session = make_mock_session()
    so = MagicMock()
    so.id = 1
    so.organization_id = 1
    so.document_no = "SO-2026-00099"
    so.status = SOStatus.DRAFT
    so.warehouse_id = 1
    line = MagicMock()
    line.id = 100
    line.sku_id = 10
    line.qty_ordered = Decimal("999999")  # larger than any available
    so.lines = [line]
    user = make_mock_user(role=RoleCode.SALES)

    repo = MagicMock()
    repo.get_detail = AsyncMock(return_value=so)

    with (
        patch("app.services.sales.SalesOrderRepository", return_value=repo),
        patch(
            "app.services.sales.inventory_svc.apply_reserve",
            new_callable=AsyncMock,
            side_effect=InsufficientStockError(
                message="Insufficient stock", detail={"sku_id": 10}
            ),
        ),
        patch("app.services.sales.event_bus.publish", new_callable=AsyncMock) as pub,
    ):
        with pytest.raises(InsufficientStockError):
            await sales_service.confirm_so(session, 1, org_id=1, user=user)

    # Status should NOT have been advanced.
    assert so.status == SOStatus.DRAFT
    # No DocumentStatusChanged event published.
    pub.assert_not_awaited()
