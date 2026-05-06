"""Persist domain events to the ``event_logs`` table for the Admin
Dev Tools page. Trims to the most recent N rows opportunistically.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy import delete, func, select

from app.core.database import AsyncSessionLocal
from app.core.logging import get_request_id
from app.events.base import DomainEvent
from app.models.audit import EventLog

logger = structlog.get_logger()

# Maximum rows to retain. Anything older than rank N gets pruned.
MAX_EVENT_LOG_ROWS = 1000

# Trim is opportunistic — only run on every Nth insert to avoid amplifying writes.
_TRIM_EVERY = 50
_insert_counter = {"n": 0}


def _serialize(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)!r} not JSON serialisable")


def _payload(event: DomainEvent) -> dict:
    if is_dataclass(event):
        # Drop the base fields that are stored as their own columns.
        raw = asdict(event)
        raw.pop("event_id", None)
        raw.pop("occurred_at", None)
    else:
        raw = {"_repr": repr(event)}
    # Round-trip through json.dumps to coerce Decimals/datetimes etc.
    return json.loads(json.dumps(raw, default=_serialize))


async def persist_event(event: DomainEvent) -> None:
    """After-commit handler — store the event for later inspection."""
    org_id = getattr(event, "organization_id", None)
    actor_id = getattr(event, "actor_user_id", None)
    payload = _payload(event)

    async with AsyncSessionLocal() as session:
        try:
            row = EventLog(
                event_type=event.event_type,
                organization_id=org_id,
                actor_user_id=actor_id,
                request_id=get_request_id() or None,
                payload=payload,
                occurred_at=event.occurred_at.replace(tzinfo=None),
            )
            session.add(row)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("event_log_insert_failed", event_type=event.event_type)
            return

    _insert_counter["n"] += 1
    if _insert_counter["n"] % _TRIM_EVERY == 0:
        await _trim()


async def _trim() -> None:
    async with AsyncSessionLocal() as session:
        try:
            total = (await session.execute(select(func.count(EventLog.id)))).scalar_one()
            if total <= MAX_EVENT_LOG_ROWS:
                return
            # Find the cutoff id — anything older than the Nth most-recent.
            offset = MAX_EVENT_LOG_ROWS
            cutoff_stmt = (
                select(EventLog.id)
                .order_by(EventLog.id.desc())
                .offset(offset)
                .limit(1)
            )
            cutoff_id = (await session.execute(cutoff_stmt)).scalar_one_or_none()
            if cutoff_id is None:
                return
            await session.execute(delete(EventLog).where(EventLog.id <= cutoff_id))
            await session.commit()
            logger.info("event_log_trimmed", cutoff_id=cutoff_id)
        except Exception:
            await session.rollback()
            logger.exception("event_log_trim_failed")
