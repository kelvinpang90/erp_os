"""Admin-only endpoints — AI settings, demo reset trigger, event-log stream.

All endpoints require ADMIN role. The Dev Tools event stream uses SSE
(no new WebSocket dependency) and fans out from the EventBus observer hook.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, AsyncIterator

import structlog
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.core.config import settings
from app.core.deps import get_db, require_role
from app.core.exceptions import AuthenticationError, AuthorizationError, NotFoundError
from app.core.security import decode_access_token
from app.enums import DemoResetStatus, DemoResetTrigger, RoleCode
from app.events import event_bus
from app.events.base import DomainEvent
from app.models.audit import DemoResetLog, EventLog
from app.models.organization import Organization, User
from app.repositories.user import UserRepository
from app.schemas.admin import (
    AISettingsResponse,
    AISettingsUpdate,
    DemoResetResponse,
    EventLogResponse,
)
from app.schemas.common import PaginatedResponse, PaginationParams

logger = structlog.get_logger()
router = APIRouter()


# ── AI settings ───────────────────────────────────────────────────────────────


def _ai_settings_payload(org: Organization) -> AISettingsResponse:
    features = dict(org.ai_features or {})
    # Ensure the three documented keys are always present in the response
    # so the toggles render predictably.
    for key in ("OCR_INVOICE", "EINVOICE_PRECHECK", "DASHBOARD_SUMMARY"):
        features.setdefault(key, True)
    return AISettingsResponse(master_enabled=org.ai_master_enabled, features=features)


@router.get("/ai-settings", response_model=AISettingsResponse, summary="Get current org AI settings")
async def get_ai_settings(
    user: User = Depends(require_role(RoleCode.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> AISettingsResponse:
    org = await db.get(Organization, user.organization_id)
    if org is None:
        raise NotFoundError(message="Organization not found.")
    return _ai_settings_payload(org)


@router.put("/ai-settings", response_model=AISettingsResponse, summary="Update org AI settings")
async def update_ai_settings(
    payload: AISettingsUpdate,
    user: User = Depends(require_role(RoleCode.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> AISettingsResponse:
    org = await db.get(Organization, user.organization_id)
    if org is None:
        raise NotFoundError(message="Organization not found.")
    org.ai_master_enabled = payload.master_enabled
    # Merge with existing so keys not provided are preserved.
    merged = dict(org.ai_features or {})
    for key, value in payload.features.items():
        merged[key] = bool(value)
    org.ai_features = merged
    db.add(org)
    await db.flush()
    return _ai_settings_payload(org)


# ── Demo reset (placeholder; full implementation lands in W18 with Celery) ────


@router.post("/demo-reset", response_model=DemoResetResponse, summary="Trigger demo data reset")
async def trigger_demo_reset(
    user: User = Depends(require_role(RoleCode.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> DemoResetResponse:
    if not settings.DEMO_MODE:
        raise AuthorizationError(
            message="Demo reset is only available when DEMO_MODE=true.",
            error_code="DEMO_MODE_REQUIRED",
        )

    log_row = DemoResetLog(
        triggered_by=DemoResetTrigger.MANUAL,
        triggered_by_user_id=user.id,
        status=DemoResetStatus.RUNNING,
    )
    db.add(log_row)
    await db.flush()
    log_id = log_row.id

    # W17: queue is symbolic — the Celery task lands in W18.
    # We immediately mark the row as "queued for execution" so the UI has
    # something to display, and the actual destructive work waits on W18.
    log_row.status = DemoResetStatus.RUNNING
    db.add(log_row)
    logger.info("demo_reset_requested", user_id=user.id, log_id=log_id)

    return DemoResetResponse(
        status="queued",
        message="Demo reset accepted. Worker integration ships in Window 18.",
        demo_reset_log_id=log_id,
    )


# ── Event log: history list + live SSE stream ────────────────────────────────


@router.get(
    "/events",
    response_model=PaginatedResponse[EventLogResponse],
    summary="Recent published events (newest first)",
)
async def list_events(
    pagination: PaginationParams = Depends(),
    event_type: str | None = Query(default=None),
    user: User = Depends(require_role(RoleCode.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[EventLogResponse]:
    base = select(EventLog).where(
        (EventLog.organization_id == user.organization_id) | (EventLog.organization_id.is_(None))
    )
    if event_type:
        base = base.where(EventLog.event_type == event_type)

    from sqlalchemy import func

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        (
            await db.execute(
                base.order_by(EventLog.id.desc()).offset(pagination.offset).limit(pagination.limit)
            )
        )
        .scalars()
        .all()
    )

    items = [
        EventLogResponse(
            id=r.id,
            event_type=r.event_type,
            organization_id=r.organization_id,
            actor_user_id=r.actor_user_id,
            request_id=r.request_id,
            payload=r.payload,
            occurred_at=r.occurred_at,
        )
        for r in rows
    ]
    return PaginatedResponse.build(
        items=items, total=total, page=pagination.page, page_size=pagination.page_size
    )


def _serialize_event(event: DomainEvent) -> dict[str, Any]:
    def _default(o: Any) -> Any:
        if isinstance(o, Decimal):
            return str(o)
        if isinstance(o, datetime):
            return o.isoformat()
        raise TypeError(f"Type {type(o)!r} not JSON serialisable")

    if is_dataclass(event):
        raw = asdict(event)
    else:
        raw = {"_repr": repr(event)}
    return {
        "event_type": event.event_type,
        "occurred_at": event.occurred_at.isoformat(),
        "payload": json.loads(json.dumps(raw, default=_default)),
    }


async def _admin_user_from_query_token(
    request: Request,
    token: str | None = Query(default=None, description="Access token (EventSource auth fallback)"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """SSE-friendly auth: accept the token from the Authorization header *or*
    the ``?token=`` query param. EventSource cannot set custom headers, so the
    Dev Tools page passes it as a query string."""
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    raw_token = token
    if not raw_token and auth and auth.lower().startswith("bearer "):
        raw_token = auth.split(" ", 1)[1].strip()
    if not raw_token:
        raise AuthenticationError(error_code="AUTHENTICATION_REQUIRED")
    payload = decode_access_token(raw_token)
    user = await UserRepository(db).get_with_roles_permissions(payload.user_id)
    if user is None or not user.is_active or user.deleted_at is not None:
        raise AuthenticationError(error_code="ACCOUNT_INACTIVE")
    if user.organization_id != payload.org_id:
        raise AuthenticationError(error_code="TOKEN_INVALID")
    role_codes = {r.code for r in user.roles} if user.roles else set()
    if RoleCode.ADMIN.value not in role_codes:
        raise AuthorizationError(message="Admin role required.")
    return user


@router.get("/events/stream", summary="Live event stream (SSE)")
async def stream_events(
    request: Request,
    user: User = Depends(_admin_user_from_query_token),
) -> EventSourceResponse:
    """Subscribe to the EventBus and forward each domain event to the client
    as an SSE message until the client disconnects."""

    queue: asyncio.Queue[DomainEvent] = asyncio.Queue(maxsize=200)
    loop = asyncio.get_running_loop()
    org_id = user.organization_id

    def _observer(event: DomainEvent) -> None:
        # Filter by org and drop silently when the queue is full so a slow
        # consumer never deadlocks the publisher.
        ev_org = getattr(event, "organization_id", None)
        if ev_org is not None and ev_org != org_id:
            return
        try:
            loop.call_soon_threadsafe(queue.put_nowait, event)
        except (asyncio.QueueFull, RuntimeError):
            return

    event_bus.subscribe_observer(_observer)

    async def _gen() -> AsyncIterator[dict[str, str]]:
        # Initial hello so EventSource knows the stream opened.
        yield {
            "event": "hello",
            "data": json.dumps({"connected_at": datetime.now(UTC).isoformat()}),
        }
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "{}"}
                    continue
                yield {"event": "domain_event", "data": json.dumps(_serialize_event(event))}
        finally:
            event_bus.unsubscribe_observer(_observer)

    return EventSourceResponse(_gen())
