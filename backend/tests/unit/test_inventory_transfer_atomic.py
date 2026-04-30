"""
Unit tests for inventory.py Window 13 helpers — the atomic SQL contracts.

Covered:
  1. apply_transfer_ship_out: returns From's avg_cost as snapshot;
     emits TRANSFER_OUT movement with source_document_type=TRANSFER.
  2. apply_transfer_ship_out: From insufficient stock raises InsufficientStockError.
  3. apply_transfer_receive: recomputes weighted-avg from snapshot;
     emits TRANSFER_IN movement.
  4. apply_adjustment_increase: defaults unit_cost to current avg_cost when None
     (preserves WAC).
  5. apply_adjustment_decrease: emits ADJUSTMENT_OUT with snapshot avg_cost.
  6. apply_adjustment_decrease: insufficient on_hand raises InsufficientStockError.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import InsufficientStockError
from app.enums import StockMovementSourceType, StockMovementType
from app.services import inventory as inventory_svc
from tests.conftest import make_mock_session


def _make_stock(
    *,
    stock_id: int = 999,
    on_hand: Decimal = Decimal("100"),
    in_transit: Decimal = Decimal("0"),
    avg_cost: Decimal = Decimal("10.0000"),
    version: int = 1,
) -> MagicMock:
    stock = MagicMock()
    stock.id = stock_id
    stock.organization_id = 1
    stock.sku_id = 11
    stock.warehouse_id = 21
    stock.on_hand = on_hand
    stock.in_transit = in_transit
    stock.avg_cost = avg_cost
    stock.reserved = Decimal("0")
    stock.quality_hold = Decimal("0")
    stock.version = version
    return stock


@pytest.mark.asyncio
async def test_transfer_ship_out_returns_snapshot_and_writes_movement():
    """ship_out returns From.avg_cost as snapshot; movement is TRANSFER_OUT/TRANSFER."""
    from_stock = _make_stock(stock_id=1, on_hand=Decimal("50"), avg_cost=Decimal("12.5000"))
    to_stock = _make_stock(stock_id=2, on_hand=Decimal("20"), in_transit=Decimal("0"))

    session = make_mock_session()
    select_from = MagicMock()
    select_from.scalar_one_or_none = MagicMock(return_value=from_stock)
    update_from = MagicMock()
    update_from.rowcount = 1
    select_to = MagicMock()
    select_to.scalar_one_or_none = MagicMock(return_value=to_stock)
    update_to = MagicMock()
    update_to.rowcount = 1
    # Order: select_from -> update_from -> select_to (in get_or_create) -> update_to.
    session.execute = AsyncMock(
        side_effect=[select_from, update_from, select_to, update_to]
    )

    with patch.object(inventory_svc.event_bus, "publish", new=AsyncMock()) as pub:
        result_from, result_to, snapshot = await inventory_svc.apply_transfer_ship_out(
            session,
            org_id=1,
            sku_id=11,
            from_warehouse_id=21,
            to_warehouse_id=22,
            qty=Decimal("10"),
            source_document_id=300,
            source_line_id=301,
            actor_user_id=7,
        )

    assert snapshot == Decimal("12.5000")
    assert result_from is from_stock
    assert result_to is to_stock

    movement = session.add.call_args_list[0].args[0]
    assert movement.movement_type == StockMovementType.TRANSFER_OUT
    assert movement.source_document_type == StockMovementSourceType.TRANSFER
    assert movement.warehouse_id == 21
    assert movement.quantity == Decimal("10")
    assert movement.unit_cost == Decimal("12.5000")
    pub.assert_awaited_once()


@pytest.mark.asyncio
async def test_transfer_ship_out_insufficient_stock_raises():
    """If From.on_hand < qty (rowcount==0), raise InsufficientStockError."""
    from_stock = _make_stock(on_hand=Decimal("3"))

    session = make_mock_session()
    select_from = MagicMock()
    select_from.scalar_one_or_none = MagicMock(return_value=from_stock)
    update_from = MagicMock()
    update_from.rowcount = 0
    session.execute = AsyncMock(side_effect=[select_from, update_from])

    with patch.object(inventory_svc.event_bus, "publish", new=AsyncMock()):
        with pytest.raises(InsufficientStockError):
            await inventory_svc.apply_transfer_ship_out(
                session,
                org_id=1,
                sku_id=11,
                from_warehouse_id=21,
                to_warehouse_id=22,
                qty=Decimal("10"),
                source_document_id=1,
            )


@pytest.mark.asyncio
async def test_transfer_receive_recomputes_avg_cost():
    """receive: avg_cost = weighted average using the From-side snapshot."""
    # To warehouse currently holds 20 @ 8 each. Receiving 10 @ snapshot=12.50.
    # New avg = (20*8 + 10*12.50) / 30 = (160 + 125) / 30 = 9.50
    to_stock = _make_stock(
        stock_id=2,
        on_hand=Decimal("20"),
        in_transit=Decimal("10"),
        avg_cost=Decimal("8.0000"),
    )

    session = make_mock_session()
    select_to = MagicMock()
    select_to.scalar_one_or_none = MagicMock(return_value=to_stock)
    update_to = MagicMock()
    update_to.rowcount = 1
    session.execute = AsyncMock(side_effect=[select_to, update_to])

    with patch.object(inventory_svc.event_bus, "publish", new=AsyncMock()) as pub:
        _, new_avg = await inventory_svc.apply_transfer_receive(
            session,
            org_id=1,
            sku_id=11,
            to_warehouse_id=22,
            qty=Decimal("10"),
            unit_cost_snapshot=Decimal("12.5000"),
            source_document_id=300,
            source_line_id=301,
        )

    assert new_avg == Decimal("9.5000")
    movement = session.add.call_args_list[0].args[0]
    assert movement.movement_type == StockMovementType.TRANSFER_IN
    assert movement.source_document_type == StockMovementSourceType.TRANSFER
    assert movement.unit_cost == Decimal("12.5000")
    assert movement.avg_cost_after == Decimal("9.5000")
    pub.assert_awaited_once()


@pytest.mark.asyncio
async def test_adjustment_increase_inherits_avg_cost_when_unit_cost_none():
    """When unit_cost is None, the new WAC must equal the existing avg_cost."""
    stock = _make_stock(on_hand=Decimal("50"), avg_cost=Decimal("7.5000"))

    session = make_mock_session()
    select_result = MagicMock()
    select_result.scalar_one_or_none = MagicMock(return_value=stock)
    update_result = MagicMock()
    update_result.rowcount = 1
    session.execute = AsyncMock(side_effect=[select_result, update_result])

    with patch.object(inventory_svc.event_bus, "publish", new=AsyncMock()):
        _, new_avg = await inventory_svc.apply_adjustment_increase(
            session,
            org_id=1,
            sku_id=11,
            warehouse_id=21,
            qty=Decimal("5"),
            unit_cost=None,  # ← inherit current avg
            source_document_id=400,
        )

    assert new_avg == Decimal("7.5000")
    movement = session.add.call_args_list[0].args[0]
    assert movement.movement_type == StockMovementType.ADJUSTMENT_IN
    assert movement.source_document_type == StockMovementSourceType.ADJUSTMENT
    assert movement.unit_cost == Decimal("7.5000")


@pytest.mark.asyncio
async def test_adjustment_decrease_emits_correct_movement():
    """Decrease writes ADJUSTMENT_OUT with snapshot avg_cost as unit_cost."""
    stock = _make_stock(on_hand=Decimal("50"), avg_cost=Decimal("9.0000"))

    session = make_mock_session()
    select_result = MagicMock()
    select_result.scalar_one_or_none = MagicMock(return_value=stock)
    update_result = MagicMock()
    update_result.rowcount = 1
    session.execute = AsyncMock(side_effect=[select_result, update_result])

    with patch.object(inventory_svc.event_bus, "publish", new=AsyncMock()) as pub:
        _, snapshot = await inventory_svc.apply_adjustment_decrease(
            session,
            org_id=1,
            sku_id=11,
            warehouse_id=21,
            qty=Decimal("3"),
            source_document_id=400,
        )

    assert snapshot == Decimal("9.0000")
    movement = session.add.call_args_list[0].args[0]
    assert movement.movement_type == StockMovementType.ADJUSTMENT_OUT
    assert movement.source_document_type == StockMovementSourceType.ADJUSTMENT
    assert movement.unit_cost == Decimal("9.0000")
    assert movement.quantity == Decimal("3")
    pub.assert_awaited_once()


@pytest.mark.asyncio
async def test_adjustment_decrease_insufficient_stock_raises():
    """Atomic guard: on_hand < qty → InsufficientStockError (rowcount==0)."""
    stock = _make_stock(on_hand=Decimal("2"))

    session = make_mock_session()
    select_result = MagicMock()
    select_result.scalar_one_or_none = MagicMock(return_value=stock)
    update_result = MagicMock()
    update_result.rowcount = 0  # WHERE on_hand >= 5 unmet
    session.execute = AsyncMock(side_effect=[select_result, update_result])

    with patch.object(inventory_svc.event_bus, "publish", new=AsyncMock()):
        with pytest.raises(InsufficientStockError):
            await inventory_svc.apply_adjustment_decrease(
                session,
                org_id=1,
                sku_id=11,
                warehouse_id=21,
                qty=Decimal("5"),
                source_document_id=1,
            )
