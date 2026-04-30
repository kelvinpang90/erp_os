"""Unit tests for InventoryService.apply_sales_return (Window 12).

Three goals (mirrors plan):
  1. on_hand increases by qty.
  2. avg_cost is the weighted average using ``unit_cost`` (= SOLine snapshot).
  3. StockMovement records movement_type=SALES_RETURN, source_type=CN —
     the audit trail must distinguish a return from a Goods Receipt.

Plus an optimistic-lock conflict guard to keep parity with apply_purchase_in.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import BusinessRuleError
from app.enums import StockMovementSourceType, StockMovementType
from app.services import inventory as inventory_svc
from tests.conftest import make_mock_session


def _make_stock(
    *,
    on_hand: Decimal = Decimal("100"),
    avg_cost: Decimal = Decimal("10.0000"),
    incoming: Decimal = Decimal("0"),
    version: int = 1,
) -> MagicMock:
    stock = MagicMock()
    stock.id = 999
    stock.organization_id = 1
    stock.sku_id = 11
    stock.warehouse_id = 21
    stock.on_hand = on_hand
    stock.avg_cost = avg_cost
    stock.incoming = incoming
    stock.version = version
    return stock


@pytest.mark.asyncio
class TestApplySalesReturn:
    async def test_increases_on_hand_and_records_sales_return_movement(self) -> None:
        """Happy path: returned units land in on_hand, movement is tagged correctly."""
        stock = _make_stock(
            on_hand=Decimal("100"),
            avg_cost=Decimal("10.0000"),
            incoming=Decimal("0"),
            version=3,
        )

        session = make_mock_session()
        update_result = MagicMock()
        update_result.rowcount = 1
        select_result = MagicMock()
        select_result.scalar_one_or_none = MagicMock(return_value=stock)
        session.execute = AsyncMock(side_effect=[select_result, update_result])

        with patch.object(inventory_svc.event_bus, "publish", new=AsyncMock()) as pub:
            result_stock, new_avg = await inventory_svc.apply_sales_return(
                session,
                org_id=1,
                sku_id=11,
                warehouse_id=21,
                qty=Decimal("10"),
                unit_cost=Decimal("8.0000"),  # snapshot from SOLine
                source_document_id=4321,
                source_line_id=8765,
                actor_user_id=42,
            )

        # 100 @ 10 + 10 @ 8 = 1080 / 110 = 9.8181... → 9.8182 with ROUND_HALF_UP
        assert new_avg == Decimal("9.8182")
        assert result_stock is stock

        adds = session.add.call_args_list
        assert len(adds) == 1
        movement = adds[0].args[0]
        # The audit row MUST distinguish a return from a Goods Receipt — this is
        # the whole reason apply_sales_return exists rather than reusing
        # apply_purchase_in.
        assert movement.movement_type == StockMovementType.SALES_RETURN
        assert movement.source_document_type == StockMovementSourceType.CN
        assert movement.source_document_id == 4321
        assert movement.source_line_id == 8765
        assert movement.quantity == Decimal("10")
        assert movement.unit_cost == Decimal("8.0000")
        assert movement.avg_cost_after == Decimal("9.8182")

        pub.assert_awaited_once()
        event = pub.await_args.args[0]
        assert event.movement_type == StockMovementType.SALES_RETURN.value
        assert event.source_document_type == StockMovementSourceType.CN.value

    async def test_avg_cost_uses_snapshot_unit_cost(self) -> None:
        """The unit_cost passed in (= SOLine.snapshot_avg_cost) drives the new avg.

        Confirming this prevents pollution: if the warehouse's avg_cost has
        drifted to 20 since the original sale at avg_cost 8, the return must
        re-introduce the original cost — not the current 20.
        """
        stock = _make_stock(
            on_hand=Decimal("0"),  # depleted, so the new avg = unit_cost exactly
            avg_cost=Decimal("20.0000"),  # current (drifted) average
            version=1,
        )

        session = make_mock_session()
        select_result = MagicMock()
        select_result.scalar_one_or_none = MagicMock(return_value=stock)
        update_result = MagicMock()
        update_result.rowcount = 1
        session.execute = AsyncMock(side_effect=[select_result, update_result])

        with patch.object(inventory_svc.event_bus, "publish", new=AsyncMock()):
            _, new_avg = await inventory_svc.apply_sales_return(
                session,
                org_id=1,
                sku_id=11,
                warehouse_id=21,
                qty=Decimal("5"),
                unit_cost=Decimal("8.0000"),  # snapshot from when goods were sold
                source_document_id=999,
            )

        # With on_hand=0, the weighted average reduces to the snapshot itself.
        assert new_avg == Decimal("8.0000")

    async def test_optimistic_lock_conflict_raises(self) -> None:
        """Concurrent stock modification → BusinessRuleError STOCK_CONFLICT."""
        stock = _make_stock(version=5)

        session = make_mock_session()
        select_result = MagicMock()
        select_result.scalar_one_or_none = MagicMock(return_value=stock)
        update_result = MagicMock()
        update_result.rowcount = 0  # someone else updated first
        session.execute = AsyncMock(side_effect=[select_result, update_result])

        with patch.object(inventory_svc.event_bus, "publish", new=AsyncMock()):
            with pytest.raises(BusinessRuleError) as exc:
                await inventory_svc.apply_sales_return(
                    session,
                    org_id=1,
                    sku_id=11,
                    warehouse_id=21,
                    qty=Decimal("5"),
                    unit_cost=Decimal("8.0000"),
                    source_document_id=1,
                )
        assert exc.value.error_code == "STOCK_CONFLICT"

    async def test_rejects_non_positive_qty(self) -> None:
        session = make_mock_session()
        with pytest.raises(ValueError):
            await inventory_svc.apply_sales_return(
                session,
                org_id=1,
                sku_id=11,
                warehouse_id=21,
                qty=Decimal("0"),
                unit_cost=Decimal("8"),
                source_document_id=1,
            )


@pytest.mark.asyncio
class TestApplySalesReturnReverse:
    """Bug fix: CN cancel needs to undo apply_sales_return without going
    through apply_sales_out (which requires reserved >= qty — a precondition
    CN inbound never establishes)."""

    async def test_only_decrements_on_hand_no_reserved_required(self) -> None:
        """The whole point: succeed even when reserved == 0."""
        stock = _make_stock(
            on_hand=Decimal("110"),     # 100 original + 10 from CN inbound
            avg_cost=Decimal("9.8182"),
            incoming=Decimal("0"),
            version=4,
        )
        # ⚠️ reserved is 0 — apply_sales_out would have failed with STOCK_CONFLICT.
        stock.reserved = Decimal("0")

        session = make_mock_session()
        update_result = MagicMock()
        update_result.rowcount = 1
        select_result = MagicMock()
        select_result.scalar_one_or_none = MagicMock(return_value=stock)
        session.execute = AsyncMock(side_effect=[select_result, update_result])

        with patch.object(inventory_svc.event_bus, "publish", new=AsyncMock()) as pub:
            result_stock = await inventory_svc.apply_sales_return_reverse(
                session,
                org_id=1,
                sku_id=11,
                warehouse_id=21,
                qty=Decimal("10"),
                source_document_id=4321,
                source_line_id=8765,
                actor_user_id=42,
                notes="CN cancellation rollback (CN-2026-00003)",
            )

        assert result_stock is stock

        # The audit row uses ADJUSTMENT_OUT + CN — the unique tuple that
        # marks "this was a CN cancellation, not a sale".
        adds = session.add.call_args_list
        assert len(adds) == 1
        movement = adds[0].args[0]
        assert movement.movement_type == StockMovementType.ADJUSTMENT_OUT
        assert movement.source_document_type == StockMovementSourceType.CN
        assert movement.source_document_id == 4321
        assert movement.quantity == Decimal("10")
        assert "CN cancellation" in (movement.notes or "")

        pub.assert_awaited_once()
        event = pub.await_args.args[0]
        assert event.movement_type == StockMovementType.ADJUSTMENT_OUT.value
        assert event.source_document_type == StockMovementSourceType.CN.value

    async def test_insufficient_on_hand_raises(self) -> None:
        """If someone consumed the returned goods before cancel, the SQL
        guard ``on_hand >= qty`` fails and we surface STOCK_CONFLICT."""
        stock = _make_stock(on_hand=Decimal("3"), version=1)

        session = make_mock_session()
        select_result = MagicMock()
        select_result.scalar_one_or_none = MagicMock(return_value=stock)
        update_result = MagicMock()
        update_result.rowcount = 0  # WHERE on_hand >= 10 unmet
        session.execute = AsyncMock(side_effect=[select_result, update_result])

        with patch.object(inventory_svc.event_bus, "publish", new=AsyncMock()):
            with pytest.raises(BusinessRuleError) as exc:
                await inventory_svc.apply_sales_return_reverse(
                    session,
                    org_id=1,
                    sku_id=11,
                    warehouse_id=21,
                    qty=Decimal("10"),
                    source_document_id=1,
                )
        assert exc.value.error_code == "STOCK_CONFLICT"

    async def test_rejects_non_positive_qty(self) -> None:
        session = make_mock_session()
        with pytest.raises(ValueError):
            await inventory_svc.apply_sales_return_reverse(
                session,
                org_id=1,
                sku_id=11,
                warehouse_id=21,
                qty=Decimal("0"),
                source_document_id=1,
            )
