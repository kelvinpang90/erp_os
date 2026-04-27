"""
In-process synchronous EventBus with after-commit deferred execution.

Usage (service layer):
    from app.events import event_bus
    from app.events.types import DocumentStatusChanged

    event = DocumentStatusChanged(...)
    await event_bus.publish(event, session)   # sync handlers run immediately;
                                              # after-commit handlers queued in session.info

The deferred handlers are drained inside get_db() after session.commit().
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

logger = structlog.get_logger()

AsyncHandler = Callable[["DomainEvent"], Coroutine[Any, Any, None]]


@dataclass
class DomainEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def event_type(self) -> str:
        return type(self).__name__


class EventBus:
    def __init__(self) -> None:
        self._sync: dict[str, list[AsyncHandler]] = {}
        self._after_commit: dict[str, list[AsyncHandler]] = {}

    def subscribe_sync(self, event_class: type[DomainEvent], handler: AsyncHandler) -> None:
        self._sync.setdefault(event_class.__name__, []).append(handler)

    def subscribe_after_commit(self, event_class: type[DomainEvent], handler: AsyncHandler) -> None:
        self._after_commit.setdefault(event_class.__name__, []).append(handler)

    async def publish(self, event: DomainEvent, session: Any) -> None:
        """Run sync handlers immediately; queue after-commit handlers in session.info."""
        key = event.event_type

        for handler in self._sync.get(key, []):
            try:
                await handler(event)
            except Exception:
                logger.exception("event_sync_handler_error", event_type=key, handler=handler.__name__)

        deferred = self._after_commit.get(key, [])
        if deferred:
            session.info.setdefault("pending_events", []).append((event, deferred))

    async def drain_after_commit(self, session: Any) -> None:
        """Called by get_db() after a successful commit to run deferred handlers."""
        pending: list[tuple[DomainEvent, list[AsyncHandler]]] = session.info.pop(
            "pending_events", []
        )
        for event, handlers in pending:
            for handler in handlers:
                try:
                    await handler(event)
                except Exception:
                    logger.exception(
                        "event_after_commit_handler_error",
                        event_type=event.event_type,
                        handler=handler.__name__,
                    )
