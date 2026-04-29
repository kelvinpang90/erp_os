"""After-commit notification handlers.

Each handler runs after the originating transaction commits. They open a
fresh session because the request session has already been disposed of.
Failures are swallowed by the EventBus to keep the user-facing request
unaffected — this is best-effort observability, not a critical write.
"""

from __future__ import annotations

import structlog

from app.core.database import AsyncSessionLocal
from app.enums import NotificationSeverity, NotificationType, RoleCode
from app.events.base import DomainEvent
from app.events.types import EInvoiceValidated
from app.models.audit import Notification

logger = structlog.get_logger()


async def notify_on_low_stock(event: DomainEvent) -> None:
    # TODO(W14): check safety_stock and create Notification record
    logger.debug("notification_stub", event_type=event.event_type)


async def notify_on_einvoice_validated(event: DomainEvent) -> None:
    """Insert a Notification row when an e-Invoice reaches VALIDATED.

    Targets the sales role for the organisation — in this demo the customer
    has no user account, so the back-office team is informed that the buyer
    now has 72h to dispute. Real production would also push to the buyer's
    portal account / email here.
    """
    if not isinstance(event, EInvoiceValidated):
        return

    async with AsyncSessionLocal() as session:
        try:
            notif = Notification(
                organization_id=event.organization_id,
                type=NotificationType.EINVOICE_VALIDATED,
                title=f"Invoice {event.invoice_no} validated by LHDN",
                body=(
                    f"UIN {event.uin} issued at {event.validated_at}. "
                    "Buyer has 72 hours to dispute (72 seconds in demo mode)."
                ),
                i18n_key="notification.einvoice_validated",
                i18n_params={
                    "invoice_no": event.invoice_no,
                    "uin": event.uin,
                    "validated_at": event.validated_at,
                },
                target_role=RoleCode.SALES.value,
                related_entity_type="INVOICE",
                related_entity_id=event.invoice_id,
                action_url=f"/app/einvoice/{event.invoice_id}",
                severity=NotificationSeverity.INFO,
            )
            session.add(notif)
            await session.commit()
            logger.info(
                "einvoice_notification_created",
                invoice_id=event.invoice_id,
                document_no=event.invoice_no,
                uin=event.uin,
            )
        except Exception:
            await session.rollback()
            logger.exception(
                "einvoice_notification_failed",
                invoice_id=event.invoice_id,
            )
