"""Unit tests for the W14 low-stock notification handler.

Focus on the branching logic — bail-out on healthy stock, bail-out on the
1-hour dedupe window, and the happy-path notification insert. Database access
is patched at the AsyncSessionLocal level so these tests don't need MySQL.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.enums import NotificationType, RoleCode
from app.events.handlers import notification as notif_handler
from app.events.types import StockMovementOccurred


def _make_stock_sku_warehouse(
    *,
    available: Decimal,
    safety_stock: Decimal,
) -> tuple[MagicMock, MagicMock, MagicMock]:
    stock = MagicMock(id=42, sku_id=10, warehouse_id=20)
    stock.on_hand = available + Decimal("0")
    stock.reserved = Decimal("0")
    stock.quality_hold = Decimal("0")
    stock.available = available

    sku = MagicMock(id=10, code="SKU-A", name="Widget", safety_stock=safety_stock)
    warehouse = MagicMock(id=20, code="WH-KL", name="KL Main")
    return stock, sku, warehouse


def _build_event() -> StockMovementOccurred:
    return StockMovementOccurred(
        organization_id=1,
        sku_id=10,
        warehouse_id=20,
        movement_type="SALES_OUT",
        quantity=Decimal("5"),
        source_document_type="DO",
        source_document_id=99,
    )


def _make_session_for_lookup(
    *,
    found_row: tuple | None,
    existing_dup_id: int | None = None,
) -> AsyncMock:
    """Build an AsyncSession mock whose two execute() calls return the
    inventory lookup then the dedupe lookup, in that order."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    inv_result = MagicMock()
    inv_result.first = MagicMock(return_value=found_row)

    dup_result = MagicMock()
    dup_result.scalar_one_or_none = MagicMock(return_value=existing_dup_id)

    session.execute = AsyncMock(side_effect=[inv_result, dup_result])
    return session


@pytest.mark.asyncio
class TestNotifyOnLowStock:
    async def test_skips_when_event_type_mismatch(self) -> None:
        """Handler is registered against StockMovementOccurred only."""
        result = await notif_handler.notify_on_low_stock(
            MagicMock(spec=[])  # arbitrary non-event object
        )
        assert result is None

    async def test_skips_when_safety_stock_zero(self) -> None:
        stock, sku, wh = _make_stock_sku_warehouse(
            available=Decimal("0"), safety_stock=Decimal("0")
        )
        session = _make_session_for_lookup(found_row=(stock, sku, wh))

        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=False)

        with patch.object(notif_handler, "AsyncSessionLocal", return_value=cm):
            await notif_handler.notify_on_low_stock(_build_event())

        session.add.assert_not_called()
        session.commit.assert_not_called()

    async def test_skips_when_available_above_safety(self) -> None:
        stock, sku, wh = _make_stock_sku_warehouse(
            available=Decimal("100"), safety_stock=Decimal("50")
        )
        session = _make_session_for_lookup(found_row=(stock, sku, wh))

        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=False)

        with patch.object(notif_handler, "AsyncSessionLocal", return_value=cm):
            await notif_handler.notify_on_low_stock(_build_event())

        session.add.assert_not_called()
        session.commit.assert_not_called()

    async def test_skips_when_recent_duplicate_exists(self) -> None:
        stock, sku, wh = _make_stock_sku_warehouse(
            available=Decimal("5"), safety_stock=Decimal("50")
        )
        session = _make_session_for_lookup(
            found_row=(stock, sku, wh), existing_dup_id=999
        )

        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=False)

        with patch.object(notif_handler, "AsyncSessionLocal", return_value=cm):
            await notif_handler.notify_on_low_stock(_build_event())

        session.add.assert_not_called()
        session.commit.assert_not_called()

    async def test_creates_notification_when_low_and_no_dup(self) -> None:
        stock, sku, wh = _make_stock_sku_warehouse(
            available=Decimal("5"), safety_stock=Decimal("50")
        )
        session = _make_session_for_lookup(
            found_row=(stock, sku, wh), existing_dup_id=None
        )

        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=False)

        with patch.object(notif_handler, "AsyncSessionLocal", return_value=cm):
            await notif_handler.notify_on_low_stock(_build_event())

        session.add.assert_called_once()
        session.commit.assert_called_once()

        notif_arg = session.add.call_args.args[0]
        assert notif_arg.organization_id == 1
        assert notif_arg.type == NotificationType.LOW_STOCK
        assert notif_arg.target_role == RoleCode.PURCHASER.value
        assert notif_arg.related_entity_type == "STOCK"
        assert notif_arg.related_entity_id == stock.id
        assert "low_stock" in notif_arg.i18n_key
        assert notif_arg.i18n_params["sku_code"] == "SKU-A"
        assert notif_arg.i18n_params["warehouse_code"] == "WH-KL"
