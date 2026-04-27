"""
Register all event handlers on startup.

Called once in main.py lifespan:
    from app.events.registry import setup_event_handlers
    from app.events import event_bus
    setup_event_handlers(event_bus)
"""

from app.events.base import EventBus
from app.events.handlers import audit, cache, inventory, notification
from app.events.types import DocumentStatusChanged, EInvoiceValidated, StockMovementOccurred


def setup_event_handlers(bus: EventBus) -> None:
    # DocumentStatusChanged — sync: audit log
    bus.subscribe_sync(DocumentStatusChanged, audit.handle_document_status_changed)

    # StockMovementOccurred — sync: audit; after-commit: cache invalidation + low-stock check
    bus.subscribe_sync(StockMovementOccurred, audit.handle_stock_movement_occurred)
    bus.subscribe_after_commit(StockMovementOccurred, cache.invalidate_dashboard_cache)
    bus.subscribe_after_commit(StockMovementOccurred, notification.notify_on_low_stock)
    bus.subscribe_after_commit(StockMovementOccurred, inventory.update_stock_on_movement)

    # EInvoiceValidated — after-commit: buyer notification
    bus.subscribe_after_commit(EInvoiceValidated, notification.notify_on_einvoice_validated)
