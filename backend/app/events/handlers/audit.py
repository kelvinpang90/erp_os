"""After-commit audit handlers.

Persist a row in ``audit_logs`` for every domain event so the three core
tables (Purchase/Sales orders, Invoices, Credit Notes — see CLAUDE.md
Part 8 audit requirement) have a complete before/after trail.

Runs after the originating transaction commits in a fresh session, so a
rolled-back parent transaction never produces an orphan audit row.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.core.database import AsyncSessionLocal
from app.core.logging import get_client_ip, get_request_id, get_user_agent
from app.enums import AuditAction
from app.events.base import DomainEvent
from app.events.types import (
    DocumentStatusChanged,
    EInvoiceValidated,
    StockMovementOccurred,
)
from app.models.audit import AuditLog

logger = structlog.get_logger()


# Map a (document_type, new_status) pair to the most specific AuditAction.
_STATUS_TO_ACTION: dict[str, AuditAction] = {
    "DRAFT": AuditAction.UPDATED,
    "CONFIRMED": AuditAction.APPROVED,
    "CANCELLED": AuditAction.CANCELLED,
    "SUBMITTED": AuditAction.SUBMITTED,
    "VALIDATED": AuditAction.VALIDATED,
    "REJECTED": AuditAction.REJECTED,
    "FINAL": AuditAction.FINALIZED,
    "FINALIZED": AuditAction.FINALIZED,
    "IN_TRANSIT": AuditAction.STATUS_CHANGED,
    "RECEIVED": AuditAction.STATUS_CHANGED,
    "PARTIAL_RECEIVED": AuditAction.STATUS_CHANGED,
    "FULLY_RECEIVED": AuditAction.STATUS_CHANGED,
    "PARTIAL_SHIPPED": AuditAction.STATUS_CHANGED,
    "FULLY_SHIPPED": AuditAction.STATUS_CHANGED,
    "INVOICED": AuditAction.STATUS_CHANGED,
    "PAID": AuditAction.STATUS_CHANGED,
}


def _resolve_action(new_status: str) -> AuditAction:
    return _STATUS_TO_ACTION.get(new_status, AuditAction.STATUS_CHANGED)


async def _insert(row: AuditLog) -> None:
    async with AsyncSessionLocal() as session:
        try:
            session.add(row)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("audit_insert_failed", entity_type=row.entity_type)


async def handle_document_status_changed(event: DomainEvent) -> None:
    if not isinstance(event, DocumentStatusChanged):
        return
    if event.document_id <= 0:
        # Batch-finalize publishes a synthetic event with id=0 — skip.
        return

    before: dict[str, Any] = {"status": event.old_status, "document_no": event.document_no}
    after: dict[str, Any] = {"status": event.new_status, "document_no": event.document_no}
    if event.before:
        before.update(event.before)
    if event.after:
        after.update(event.after)

    row = AuditLog(
        organization_id=event.organization_id,
        entity_type=event.document_type,
        entity_id=event.document_id,
        action=_resolve_action(event.new_status),
        actor_user_id=event.actor_user_id,
        before=before,
        after=after,
        ip=get_client_ip() or None,
        user_agent=get_user_agent() or None,
        request_id=get_request_id() or None,
    )
    await _insert(row)


async def handle_einvoice_validated(event: DomainEvent) -> None:
    if not isinstance(event, EInvoiceValidated):
        return

    row = AuditLog(
        organization_id=event.organization_id,
        entity_type="INVOICE",
        entity_id=event.invoice_id,
        action=AuditAction.VALIDATED,
        actor_user_id=None,
        before=None,
        after={
            "uin": event.uin,
            "invoice_no": event.invoice_no,
            "validated_at": event.validated_at,
        },
        ip=get_client_ip() or None,
        user_agent=get_user_agent() or None,
        request_id=get_request_id() or None,
    )
    await _insert(row)


async def handle_stock_movement_occurred(event: DomainEvent) -> None:
    """Lightweight log only — stock movements are already persisted in
    ``stock_movements`` so we don't duplicate them in ``audit_logs``."""
    if not isinstance(event, StockMovementOccurred):
        return
    logger.info(
        "audit_stock_movement",
        event_type=event.event_type,
        sku_id=event.sku_id,
        warehouse_id=event.warehouse_id,
        movement_type=event.movement_type,
    )
