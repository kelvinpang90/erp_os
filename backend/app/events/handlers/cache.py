import structlog

from app.events.base import DomainEvent

logger = structlog.get_logger()


async def invalidate_dashboard_cache(event: DomainEvent) -> None:
    # TODO(W15): del redis_cache keys for dashboard aggregates
    logger.debug("cache_invalidation_stub", event_type=event.event_type)
