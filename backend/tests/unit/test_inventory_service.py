"""Unit tests for InventoryService.apply_purchase_in (Window 8)."""

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
    incoming: Decimal = Decimal("50"),
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
class TestApplyPurchaseIn:
    async def test_creates_movement_and_updates_stock(self) -> None:
        """Happy path: existing stock row + version match → update succeeds."""
        stock = _make_stock(
            on_hand=Decimal("100"),
            avg_cost=Decimal("10.0000"),
            incoming=Decimal("50"),
            version=3,
        )

        session = make_mock_session()
        # First execute() = get_or_create (returns stock).
        # Second execute() = atomic UPDATE (rowcount=1).
        update_result = MagicMock()
        update_result.rowcount = 1
        select_result = MagicMock()
        select_result.scalar_one_or_none = MagicMock(return_value=stock)
        session.execute = AsyncMock(side_effect=[select_result, update_result])

        with patch.object(inventory_svc.event_bus, "publish", new=AsyncMock()) as pub:
            result_stock, new_avg = await inventory_svc.apply_purchase_in(
                session,
                org_id=1,
                sku_id=11,
                warehouse_id=21,
                qty=Decimal("50"),
                unit_cost=Decimal("16.0000"),
                source_document_id=1234,
                source_line_id=5678,
                actor_user_id=42,
            )

        # 100 @ 10 + 50 @ 16 = 1000 + 800 = 1800 / 150 = 12.0000
        assert new_avg == Decimal("12.0000")
        assert result_stock is stock

        # session.add called twice: once may be _get_or_create (no), since stock
        # already exists; once for the StockMovement.
        adds = session.add.call_args_list
        assert len(adds) == 1
        movement = adds[0].args[0]
        assert movement.movement_type == StockMovementType.PURCHASE_IN
        assert movement.source_document_type == StockMovementSourceType.GR
        assert movement.source_document_id == 1234
        assert movement.source_line_id == 5678
        assert movement.quantity == Decimal("50")
        assert movement.unit_cost == Decimal("16.0000")
        assert movement.avg_cost_after == Decimal("12.0000")

        # Event published with correct payload.
        pub.assert_awaited_once()
        event = pub.await_args.args[0]
        assert event.sku_id == 11
        assert event.warehouse_id == 21
        assert event.movement_type == StockMovementType.PURCHASE_IN.value
        assert event.source_document_type == StockMovementSourceType.GR.value

    async def test_creates_stock_when_not_exist(self) -> None:
        """First-ever receipt: stock row created via session.add then update."""
        session = make_mock_session()
        select_result = MagicMock()
        select_result.scalar_one_or_none = MagicMock(return_value=None)

        # The newly-added Stock is the same object referenced after refresh.
        # session.add is sync — capture the new Stock instance for assertions.
        added_stock_holder: list = []

        def _capture_add(obj):
            # Simulate DB defaults so the .version attr is initialized.
            if hasattr(obj, "on_hand"):
                obj.id = 1
                obj.version = 1
            added_stock_holder.append(obj)

        session.add.side_effect = _capture_add

        update_result = MagicMock()
        update_result.rowcount = 1
        session.execute = AsyncMock(side_effect=[select_result, update_result])

        with patch.object(inventory_svc.event_bus, "publish", new=AsyncMock()):
            stock, new_avg = await inventory_svc.apply_purchase_in(
                session,
                org_id=1,
                sku_id=11,
                warehouse_id=21,
                qty=Decimal("80"),
                unit_cost=Decimal("12.5000"),
                source_document_id=10,
            )

        # Empty stock + 80 @ 12.5 → avg = 12.5000
        assert new_avg == Decimal("12.5000")
        # session.add called twice: new Stock + new StockMovement.
        assert session.add.call_count == 2

    async def test_optimistic_lock_conflict_raises(self) -> None:
        """When concurrent update changed version, rowcount=0 → BusinessRuleError."""
        stock = _make_stock()
        session = make_mock_session()
        select_result = MagicMock()
        select_result.scalar_one_or_none = MagicMock(return_value=stock)
        update_result = MagicMock()
        update_result.rowcount = 0  # Simulated concurrent modification.
        session.execute = AsyncMock(side_effect=[select_result, update_result])

        with patch.object(inventory_svc.event_bus, "publish", new=AsyncMock()):
            with pytest.raises(BusinessRuleError) as exc_info:
                await inventory_svc.apply_purchase_in(
                    session,
                    org_id=1,
                    sku_id=11,
                    warehouse_id=21,
                    qty=Decimal("10"),
                    unit_cost=Decimal("5"),
                    source_document_id=1,
                )

        assert exc_info.value.error_code == "STOCK_CONFLICT"

    @pytest.mark.parametrize(
        "qty,unit_cost",
        [
            (Decimal("0"), Decimal("10")),    # qty == 0
            (Decimal("-1"), Decimal("10")),   # qty negative
            (Decimal("10"), Decimal("-1")),   # unit_cost negative
        ],
    )
    async def test_invalid_args_raise_value_error(
        self, qty: Decimal, unit_cost: Decimal
    ) -> None:
        session = make_mock_session()
        with pytest.raises(ValueError):
            await inventory_svc.apply_purchase_in(
                session,
                org_id=1,
                sku_id=11,
                warehouse_id=21,
                qty=qty,
                unit_cost=unit_cost,
                source_document_id=1,
            )
