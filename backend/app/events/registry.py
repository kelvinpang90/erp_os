"""
Register all event handlers on startup.

Called once in main.py lifespan:
    from app.events.registry import setup_event_handlers
    from app.events import event_bus
    setup_event_handlers(event_bus)
"""

from app.events.base import EventBus
from app.events.handlers import audit, cache, event_log, inventory, notification
from app.events.types import DocumentStatusChanged, EInvoiceValidated, StockMovementOccurred


def setup_event_handlers(bus: EventBus) -> None:
    # DocumentStatusChanged — after-commit: audit row + cache drop + event_logs row.
    bus.subscribe_after_commit(DocumentStatusChanged, audit.handle_document_status_changed)
    bus.subscribe_after_commit(DocumentStatusChanged, cache.invalidate_dashboard_cache)
    bus.subscribe_after_commit(DocumentStatusChanged, event_log.persist_event)

    # StockMovementOccurred — sync: lightweight log; after-commit: cache + low-stock + matrix
    bus.subscribe_sync(StockMovementOccurred, audit.handle_stock_movement_occurred)
    bus.subscribe_after_commit(StockMovementOccurred, cache.invalidate_dashboard_cache)
    bus.subscribe_after_commit(StockMovementOccurred, notification.notify_on_low_stock)
    bus.subscribe_after_commit(StockMovementOccurred, inventory.update_stock_on_movement)
    bus.subscribe_after_commit(StockMovementOccurred, event_log.persist_event)

    # EInvoiceValidated — after-commit: audit row + buyer notification + cache drop + log
    bus.subscribe_after_commit(EInvoiceValidated, audit.handle_einvoice_validated)
    bus.subscribe_after_commit(EInvoiceValidated, notification.notify_on_einvoice_validated)
    bus.subscribe_after_commit(EInvoiceValidated, cache.invalidate_dashboard_cache)
    bus.subscribe_after_commit(EInvoiceValidated, event_log.persist_event)
