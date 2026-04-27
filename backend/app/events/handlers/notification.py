import structlog

from app.events.base import DomainEvent

logger = structlog.get_logger()


async def notify_on_low_stock(event: DomainEvent) -> None:
    # TODO(W14): check safety_stock and create Notification record
    logger.debug("notification_stub", event_type=event.event_type)


async def notify_on_einvoice_validated(event: DomainEvent) -> None:
    # TODO(W11): push notification to buyer
    logger.debug("einvoice_notification_stub", event_type=event.event_type)
