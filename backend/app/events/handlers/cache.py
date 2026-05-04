"""Cache invalidation handler — drops dashboard aggregates on key events.

Listens on the three core domain events; KPI + trends caches are dropped
so the next /api/dashboard/overview call reflects fresh state. The AI
summary cache is intentionally left alone — its 30-min TTL is the
freshness budget, and we don't want to burn LLM tokens on every stock
move.
"""

from __future__ import annotations

import structlog

from app.events.base import DomainEvent
from app.events.types import (
    DocumentStatusChanged,
    EInvoiceValidated,
    StockMovementOccurred,
)
from app.services.dashboard import invalidate_caches

logger = structlog.get_logger()


def _resolve_org_id(event: DomainEvent) -> int | None:
    """Best-effort organization_id extraction across event subclasses."""
    org_id = getattr(event, "organization_id", None)
    if isinstance(org_id, int) and org_id > 0:
        return org_id
    return None


async def invalidate_dashboard_cache(event: DomainEvent) -> None:
    """After-commit hook — drop KPI / trends Redis keys for the org."""
    if not isinstance(
        event, (StockMovementOccurred, DocumentStatusChanged, EInvoiceValidated)
    ):
        return

    org_id = _resolve_org_id(event)
    if org_id is None:
        logger.debug(
            "cache_invalidation_skipped_no_org", event_type=event.event_type
        )
        return

    try:
        await invalidate_caches(org_id)
    except Exception:  # noqa: BLE001 — handlers must never raise
        logger.exception(
            "cache_invalidation_failed",
            event_type=event.event_type,
            organization_id=org_id,
        )
        return

    logger.debug(
        "dashboard_cache_invalidated",
        event_type=event.event_type,
        organization_id=org_id,
    )
