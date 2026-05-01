"""After-commit notification handlers.

Each handler runs after the originating transaction commits. They open a
fresh session because the request session has already been disposed of.
Failures are swallowed by the EventBus to keep the user-facing request
unaffected — this is best-effort observability, not a critical write.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import structlog
from sqlalchemy import and_, select

from app.core.database import AsyncSessionLocal
from app.enums import NotificationSeverity, NotificationType, RoleCode
from app.events.base import DomainEvent
from app.events.types import EInvoiceValidated, StockMovementOccurred
from app.models.audit import Notification
from app.models.organization import Warehouse
from app.models.sku import SKU
from app.models.stock import Stock

logger = structlog.get_logger()


_LOW_STOCK_DEDUP_WINDOW = timedelta(hours=1)


async def notify_on_low_stock(event: DomainEvent) -> None:
    """Create a LOW_STOCK Notification when a movement drops available below safety.

    Triggered after-commit on every ``StockMovementOccurred``. Steps:
    1. Re-read the (sku, warehouse) Stock + SKU.safety_stock in a fresh session.
    2. Bail out if safety_stock is zero (no policy) or available is still
       above the threshold.
    3. Dedupe: skip if an unread LOW_STOCK notification for the same
       (sku, warehouse) was already created in the last hour — otherwise
       every outbound movement on a low SKU would spam the bell.
    4. Insert a Notification targeted at the PURCHASER role with an
       action_url pointing back to the alerts page.
    """
    if not isinstance(event, StockMovementOccurred):
        return

    async with AsyncSessionLocal() as session:
        try:
            stmt = (
                select(Stock, SKU, Warehouse)
                .join(SKU, SKU.id == Stock.sku_id)
                .join(Warehouse, Warehouse.id == Stock.warehouse_id)
                .where(
                    Stock.sku_id == event.sku_id,
                    Stock.warehouse_id == event.warehouse_id,
                )
            )
            row = (await session.execute(stmt)).first()
            if row is None:
                return
            stock, sku, warehouse = row

            if sku.safety_stock is None or sku.safety_stock <= Decimal("0"):
                return
            available = stock.available
            if available is None:
                available = stock.on_hand - stock.reserved - stock.quality_hold
            if available >= sku.safety_stock:
                return

            cutoff = datetime.now(UTC).replace(tzinfo=None) - _LOW_STOCK_DEDUP_WINDOW
            recent_stmt = (
                select(Notification.id)
                .where(
                    and_(
                        Notification.organization_id == event.organization_id,
                        Notification.type == NotificationType.LOW_STOCK,
                        Notification.related_entity_type == "STOCK",
                        Notification.related_entity_id == stock.id,
                        Notification.is_read.is_(False),
                        Notification.created_at >= cutoff,
                    )
                )
                .limit(1)
            )
            existing = (await session.execute(recent_stmt)).scalar_one_or_none()
            if existing is not None:
                logger.debug(
                    "low_stock_notification_deduped",
                    sku_id=sku.id,
                    warehouse_id=warehouse.id,
                )
                return

            shortage = sku.safety_stock - available
            notif = Notification(
                organization_id=event.organization_id,
                type=NotificationType.LOW_STOCK,
                title=f"Low stock: {sku.code} at {warehouse.code}",
                body=(
                    f"Available {available} is below safety stock "
                    f"{sku.safety_stock} (short by {shortage})."
                ),
                i18n_key="notification.low_stock",
                i18n_params={
                    "sku_code": sku.code,
                    "sku_name": sku.name,
                    "warehouse_code": warehouse.code,
                    "warehouse_name": warehouse.name,
                    "available": str(available),
                    "safety_stock": str(sku.safety_stock),
                    "shortage": str(shortage),
                },
                target_role=RoleCode.PURCHASER.value,
                related_entity_type="STOCK",
                related_entity_id=stock.id,
                action_url=f"/app/inventory/alerts?sku_id={sku.id}",
                severity=NotificationSeverity.WARNING,
            )
            session.add(notif)
            await session.commit()
            logger.info(
                "low_stock_notification_created",
                sku_id=sku.id,
                sku_code=sku.code,
                warehouse_id=warehouse.id,
                available=str(available),
                safety_stock=str(sku.safety_stock),
            )
        except Exception:
            await session.rollback()
            logger.exception(
                "low_stock_notification_failed",
                sku_id=event.sku_id,
                warehouse_id=event.warehouse_id,
            )


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
