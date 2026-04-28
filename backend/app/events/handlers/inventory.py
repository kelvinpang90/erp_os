"""After-commit side-effects for StockMovementOccurred.

The actual Stock-row mutation happens in services/inventory.py (Window 8)
inside the originating transaction. This handler runs *after* commit and is
reserved for non-critical side-effects such as:

* low-stock alert notifications  (W14)
* dashboard / hot-cache invalidation (W15)
* secondary observability hooks

We keep the function lightweight and never raise — the EventBus already
swallows handler exceptions, but a noisy handler still produces log noise.
"""

from __future__ import annotations

import structlog

from app.events.base import DomainEvent
from app.events.types import StockMovementOccurred

logger = structlog.get_logger()


async def update_stock_on_movement(event: DomainEvent) -> None:
    """After-commit hook fired by every StockMovementOccurred publish.

    Window 8 only emits structured logs here. Real notification + cache
    invalidation logic land in their respective windows.
    """
    if not isinstance(event, StockMovementOccurred):
        return

    logger.debug(
        "stock_movement_observed",
        org_id=event.organization_id,
        sku_id=event.sku_id,
        warehouse_id=event.warehouse_id,
        movement_type=event.movement_type,
        quantity=str(event.quantity),
        source_document_type=event.source_document_type,
        source_document_id=event.source_document_id,
    )

    # TODO(W14): low-stock check
    #   if available + incoming < sku.safety_stock: enqueue notification
    # TODO(W15): redis cache invalidation
    #   await redis.delete(f"dashboard:stock:{org_id}", ...)
