import structlog

from app.events.base import DomainEvent

logger = structlog.get_logger()


async def update_stock_on_movement(event: DomainEvent) -> None:
    # TODO(W8): update Stock 6-dim fields on StockMovementOccurred
    logger.debug("inventory_handler_stub", event_type=event.event_type)
