"""Unit tests for the W15 cache-invalidation event handler.

The handler subscribes to three core events and is required to never raise.
We verify it routes to ``invalidate_caches`` only for known event types and
correctly extracts the organization_id from each.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.events.handlers import cache as cache_handler
from app.events.types import (
    DocumentStatusChanged,
    EInvoiceValidated,
    StockMovementOccurred,
)


@pytest.mark.asyncio
class TestInvalidateDashboardCacheHandler:
    async def test_stock_movement_invalidates(self) -> None:
        event = StockMovementOccurred(
            organization_id=11,
            sku_id=1,
            warehouse_id=2,
            movement_type="SALES_OUT",
            quantity=Decimal("3"),
            source_document_type="DO",
            source_document_id=99,
        )
        with patch.object(
            cache_handler, "invalidate_caches", new=AsyncMock()
        ) as inv_mock:
            await cache_handler.invalidate_dashboard_cache(event)
        inv_mock.assert_awaited_once_with(11)

    async def test_document_status_changed_invalidates(self) -> None:
        event = DocumentStatusChanged(
            document_type="SO",
            document_id=1,
            document_no="SO-2026-1",
            old_status="DRAFT",
            new_status="CONFIRMED",
            organization_id=22,
        )
        with patch.object(
            cache_handler, "invalidate_caches", new=AsyncMock()
        ) as inv_mock:
            await cache_handler.invalidate_dashboard_cache(event)
        inv_mock.assert_awaited_once_with(22)

    async def test_einvoice_validated_invalidates(self) -> None:
        event = EInvoiceValidated(
            organization_id=33,
            invoice_id=1,
            invoice_no="INV-1",
            uin="U-1",
            validated_at="2026-05-04T00:00:00",
        )
        with patch.object(
            cache_handler, "invalidate_caches", new=AsyncMock()
        ) as inv_mock:
            await cache_handler.invalidate_dashboard_cache(event)
        inv_mock.assert_awaited_once_with(33)

    async def test_unknown_event_is_ignored(self) -> None:
        event = MagicMock(spec=[])  # not a DomainEvent subclass we know
        with patch.object(
            cache_handler, "invalidate_caches", new=AsyncMock()
        ) as inv_mock:
            await cache_handler.invalidate_dashboard_cache(event)
        inv_mock.assert_not_called()

    async def test_swallows_invalidate_exceptions(self) -> None:
        """Handlers must never propagate exceptions back to the event bus."""
        event = StockMovementOccurred(
            organization_id=44,
            sku_id=1,
            warehouse_id=2,
            movement_type="SALES_OUT",
            quantity=Decimal("3"),
            source_document_type="DO",
            source_document_id=99,
        )
        with patch.object(
            cache_handler,
            "invalidate_caches",
            new=AsyncMock(side_effect=RuntimeError("redis down")),
        ):
            # Should not raise.
            await cache_handler.invalidate_dashboard_cache(event)
