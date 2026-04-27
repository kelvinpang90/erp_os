import structlog

from app.events.base import DomainEvent

logger = structlog.get_logger()


async def handle_document_status_changed(event: DomainEvent) -> None:
    # TODO(W17): write to audit_logs table
    logger.info(
        "audit_event",
        event_type=event.event_type,
        event_id=event.event_id,
    )


async def handle_stock_movement_occurred(event: DomainEvent) -> None:
    logger.info(
        "audit_stock_movement",
        event_type=event.event_type,
        event_id=event.event_id,
    )
