"""Stock Transfer service — CRUD + 4-state state machine.

State machine (Window 13):
    DRAFT ──confirm──▶ CONFIRMED ──ship_out──▶ IN_TRANSIT ──receive (full)──▶ RECEIVED
                                                       │     (partial)        │
                                                       └─── stay IN_TRANSIT ──┘
    DRAFT     ──cancel──▶ CANCELLED
    CONFIRMED ──cancel──▶ CANCELLED  (Manager / Admin only)
    IN_TRANSIT / RECEIVED → CANCELLED is forbidden (goods are physically moving).

Inventory side-effects:
    confirm    — none (pure approval).
    ship_out   — From.on_hand -= qty, To.in_transit += qty, snapshot avg_cost
                 written to each line.
    receive    — To.in_transit -= qty, To.on_hand += qty, recompute avg_cost
                 using the snapshot. Partial receives accumulate onto
                 line.qty_received until all lines are full.
    cancel (CONFIRMED) — none, since CONFIRMED did not move stock.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthorizationError,
    BusinessRuleError,
    InvalidStatusTransitionError,
    NotFoundError,
    ValidationError,
)
from app.enums import RoleCode, StockTransferStatus
from app.events import event_bus
from app.events.types import DocumentStatusChanged
from app.models.organization import User
from app.models.stock import StockTransfer, StockTransferLine
from app.repositories.stock_transfer import StockTransferRepository
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.stock_transfer import (
    StockTransferCancel,
    StockTransferCreate,
    StockTransferDetail,
    StockTransferLineCreate,
    StockTransferLineResponse,
    StockTransferReceiveLine,
    StockTransferReceiveRequest,
    StockTransferResponse,
    StockTransferUpdate,
)
from app.services import inventory as inventory_svc
from app.services.sequence import next_document_no

logger = structlog.get_logger()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _utc_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _user_has_role(user: User, *codes: RoleCode) -> bool:
    if not user.roles:
        return False
    user_codes = {r.code for r in user.roles}
    allowed = {c.value for c in codes}
    return bool(user_codes & allowed)


def _to_response(transfer: StockTransfer) -> StockTransferDetail:
    lines = []
    for ln in transfer.lines or []:
        resp = StockTransferLineResponse.model_validate(ln)
        resp.sku_code = ln.sku.code if ln.sku else ""
        resp.sku_name = ln.sku.name if ln.sku else ""
        lines.append(resp)
    detail = StockTransferDetail.model_validate(transfer)
    detail.lines = lines
    detail.from_warehouse_name = (
        transfer.from_warehouse.name if transfer.from_warehouse is not None else ""
    )
    detail.to_warehouse_name = (
        transfer.to_warehouse.name if transfer.to_warehouse is not None else ""
    )
    return detail


def _validate_warehouses_distinct(from_id: int, to_id: int) -> None:
    if from_id == to_id:
        raise ValidationError(
            message="from_warehouse and to_warehouse must differ.",
            error_code="TRANSFER_SAME_WAREHOUSE",
        )


# ── Public API ────────────────────────────────────────────────────────────────


async def list_transfers(
    session: AsyncSession,
    pagination: PaginationParams,
    *,
    org_id: int,
    status: StockTransferStatus | None = None,
    from_warehouse_id: int | None = None,
    to_warehouse_id: int | None = None,
    search: str | None = None,
) -> PaginatedResponse[StockTransferResponse]:
    repo = StockTransferRepository(session)
    items, total = await repo.list_with_filters(
        org_id,
        status=status,
        from_warehouse_id=from_warehouse_id,
        to_warehouse_id=to_warehouse_id,
        search=search,
        limit=pagination.page_size,
        offset=pagination.offset,
    )
    return PaginatedResponse[StockTransferResponse].build(
        items=[StockTransferResponse.model_validate(t) for t in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


async def get_transfer(
    session: AsyncSession,
    transfer_id: int,
    *,
    org_id: int,
) -> StockTransferDetail:
    repo = StockTransferRepository(session)
    transfer = await repo.get_detail(org_id, transfer_id)
    if transfer is None:
        raise NotFoundError(message=f"Stock transfer {transfer_id} not found.")
    return _to_response(transfer)


async def create_transfer(
    session: AsyncSession,
    data: StockTransferCreate,
    *,
    org_id: int,
    user: User,
) -> StockTransferDetail:
    _validate_warehouses_distinct(data.from_warehouse_id, data.to_warehouse_id)

    document_no = await next_document_no(session, "TR", org_id)

    transfer = StockTransfer(
        organization_id=org_id,
        document_no=document_no,
        status=StockTransferStatus.DRAFT,
        from_warehouse_id=data.from_warehouse_id,
        to_warehouse_id=data.to_warehouse_id,
        business_date=data.business_date,
        expected_arrival_date=data.expected_arrival_date,
        remarks=data.remarks,
        created_by=user.id,
        updated_by=user.id,
    )
    session.add(transfer)
    await session.flush()

    for idx, ln in enumerate(data.lines):
        session.add(
            StockTransferLine(
                stock_transfer_id=transfer.id,
                line_no=idx + 1,
                sku_id=ln.sku_id,
                uom_id=ln.uom_id,
                qty_sent=ln.qty_sent,
                qty_received=Decimal("0"),
                unit_cost_snapshot=None,
                batch_no=ln.batch_no,
                expiry_date=ln.expiry_date,
            )
        )

    await session.flush()
    repo = StockTransferRepository(session)
    transfer = await repo.get_detail(org_id, transfer.id)  # type: ignore[assignment]

    logger.info(
        "stock_transfer_created",
        transfer_id=transfer.id,  # type: ignore[union-attr]
        document_no=transfer.document_no,  # type: ignore[union-attr]
        org_id=org_id,
    )
    return _to_response(transfer)  # type: ignore[arg-type]


async def update_transfer(
    session: AsyncSession,
    transfer_id: int,
    data: StockTransferUpdate,
    *,
    org_id: int,
    user: User,
) -> StockTransferDetail:
    repo = StockTransferRepository(session)
    transfer = await repo.get_detail(org_id, transfer_id)
    if transfer is None:
        raise NotFoundError(message=f"Stock transfer {transfer_id} not found.")
    if transfer.status != StockTransferStatus.DRAFT:
        raise BusinessRuleError(
            message="Only DRAFT stock transfers can be edited.",
            error_code="TRANSFER_NOT_EDITABLE",
        )

    new_from = data.from_warehouse_id or transfer.from_warehouse_id
    new_to = data.to_warehouse_id or transfer.to_warehouse_id
    _validate_warehouses_distinct(new_from, new_to)

    if data.from_warehouse_id is not None:
        transfer.from_warehouse_id = data.from_warehouse_id
    if data.to_warehouse_id is not None:
        transfer.to_warehouse_id = data.to_warehouse_id
    if data.business_date is not None:
        transfer.business_date = data.business_date
    if data.expected_arrival_date is not None:
        transfer.expected_arrival_date = data.expected_arrival_date
    if data.remarks is not None:
        transfer.remarks = data.remarks
    transfer.updated_by = user.id

    if data.lines is not None:
        for line in transfer.lines:
            await session.delete(line)
        await session.flush()
        for idx, ln in enumerate(data.lines):
            session.add(
                StockTransferLine(
                    stock_transfer_id=transfer.id,
                    line_no=idx + 1,
                    sku_id=ln.sku_id,
                    uom_id=ln.uom_id,
                    qty_sent=ln.qty_sent,
                    qty_received=Decimal("0"),
                    unit_cost_snapshot=None,
                    batch_no=ln.batch_no,
                    expiry_date=ln.expiry_date,
                )
            )

    session.add(transfer)
    await session.flush()
    transfer = await repo.get_detail(org_id, transfer_id)  # type: ignore[assignment]
    return _to_response(transfer)  # type: ignore[arg-type]


async def confirm_transfer(
    session: AsyncSession,
    transfer_id: int,
    *,
    org_id: int,
    user: User,
) -> StockTransferDetail:
    """DRAFT → CONFIRMED. Pure approval, no inventory impact."""
    repo = StockTransferRepository(session)
    transfer = await repo.get_detail(org_id, transfer_id)
    if transfer is None:
        raise NotFoundError(message=f"Stock transfer {transfer_id} not found.")
    if transfer.status != StockTransferStatus.DRAFT:
        raise InvalidStatusTransitionError(
            message=(
                f"Cannot confirm a stock transfer in {transfer.status.value} status."
            )
        )
    if not transfer.lines:
        raise BusinessRuleError(
            message="Cannot confirm a stock transfer with no lines.",
            error_code="TRANSFER_NO_LINES",
        )

    old_status = transfer.status.value
    transfer.status = StockTransferStatus.CONFIRMED
    transfer.updated_by = user.id
    session.add(transfer)

    await event_bus.publish(
        DocumentStatusChanged(
            document_type="TRANSFER",
            document_id=transfer.id,
            document_no=transfer.document_no,
            old_status=old_status,
            new_status=StockTransferStatus.CONFIRMED.value,
            organization_id=org_id,
            actor_user_id=user.id,
        ),
        session,
    )

    await session.flush()
    transfer = await repo.get_detail(org_id, transfer_id)  # type: ignore[assignment]
    logger.info(
        "stock_transfer_confirmed",
        transfer_id=transfer_id,
        document_no=transfer.document_no,  # type: ignore[union-attr]
    )
    return _to_response(transfer)  # type: ignore[arg-type]


async def ship_out_transfer(
    session: AsyncSession,
    transfer_id: int,
    *,
    org_id: int,
    user: User,
) -> StockTransferDetail:
    """CONFIRMED → IN_TRANSIT.

    For each line:
      * From.on_hand -= qty_sent (atomic, may raise InsufficientStockError)
      * To.in_transit += qty_sent
      * Persist From.avg_cost into line.unit_cost_snapshot for the receive leg.
    """
    repo = StockTransferRepository(session)
    transfer = await repo.get_detail(org_id, transfer_id)
    if transfer is None:
        raise NotFoundError(message=f"Stock transfer {transfer_id} not found.")
    if transfer.status != StockTransferStatus.CONFIRMED:
        raise InvalidStatusTransitionError(
            message=(
                f"Cannot ship a stock transfer in {transfer.status.value} status."
            )
        )

    for line in transfer.lines:
        _, _, snapshot = await inventory_svc.apply_transfer_ship_out(
            session,
            org_id=org_id,
            sku_id=line.sku_id,
            from_warehouse_id=transfer.from_warehouse_id,
            to_warehouse_id=transfer.to_warehouse_id,
            qty=line.qty_sent,
            source_document_id=transfer.id,
            source_line_id=line.id,
            batch_no=line.batch_no,
            expiry_date=line.expiry_date,
            actor_user_id=user.id,
            notes=f"Transfer {transfer.document_no}",
        )
        line.unit_cost_snapshot = snapshot
        session.add(line)

    old_status = transfer.status.value
    transfer.status = StockTransferStatus.IN_TRANSIT
    transfer.updated_by = user.id
    session.add(transfer)

    await event_bus.publish(
        DocumentStatusChanged(
            document_type="TRANSFER",
            document_id=transfer.id,
            document_no=transfer.document_no,
            old_status=old_status,
            new_status=StockTransferStatus.IN_TRANSIT.value,
            organization_id=org_id,
            actor_user_id=user.id,
        ),
        session,
    )

    await session.flush()
    transfer = await repo.get_detail(org_id, transfer_id)  # type: ignore[assignment]
    logger.info(
        "stock_transfer_shipped",
        transfer_id=transfer_id,
        document_no=transfer.document_no,  # type: ignore[union-attr]
    )
    return _to_response(transfer)  # type: ignore[arg-type]


async def receive_transfer(
    session: AsyncSession,
    transfer_id: int,
    data: StockTransferReceiveRequest,
    *,
    org_id: int,
    user: User,
) -> StockTransferDetail:
    """IN_TRANSIT → IN_TRANSIT (partial) or RECEIVED (full).

    Each receive payload accumulates onto line.qty_received. When all lines
    have qty_received == qty_sent, the header transitions to RECEIVED and
    actual_arrival_date is stamped.
    """
    repo = StockTransferRepository(session)
    transfer = await repo.get_detail(org_id, transfer_id)
    if transfer is None:
        raise NotFoundError(message=f"Stock transfer {transfer_id} not found.")
    if transfer.status != StockTransferStatus.IN_TRANSIT:
        raise InvalidStatusTransitionError(
            message=(
                f"Cannot receive a stock transfer in {transfer.status.value} status."
            )
        )

    line_map: dict[int, StockTransferLine] = {ln.id: ln for ln in transfer.lines}
    for payload in data.lines:
        line = line_map.get(payload.line_id)
        if line is None:
            raise ValidationError(
                message=f"Line id {payload.line_id} does not belong to this transfer.",
                error_code="TRANSFER_LINE_NOT_FOUND",
            )
        new_received = (line.qty_received or Decimal("0")) + payload.qty_received
        if new_received > line.qty_sent:
            raise BusinessRuleError(
                message=(
                    f"Line {line.line_no}: cumulative qty_received {new_received} "
                    f"would exceed qty_sent {line.qty_sent}."
                ),
                error_code="TRANSFER_RECEIVE_OVER",
            )
        snapshot = line.unit_cost_snapshot
        if snapshot is None:
            # Defensive: should always be set by ship_out. Fall back to 0 to
            # avoid recompute crash; demo continues without crash.
            snapshot = Decimal("0")
        await inventory_svc.apply_transfer_receive(
            session,
            org_id=org_id,
            sku_id=line.sku_id,
            to_warehouse_id=transfer.to_warehouse_id,
            qty=payload.qty_received,
            unit_cost_snapshot=snapshot,
            source_document_id=transfer.id,
            source_line_id=line.id,
            batch_no=line.batch_no,
            expiry_date=line.expiry_date,
            actor_user_id=user.id,
            notes=f"Transfer {transfer.document_no} receive",
        )
        line.qty_received = new_received
        session.add(line)

    # Decide whether the transfer is fully received.
    fully_received = all(
        (ln.qty_received or Decimal("0")) >= ln.qty_sent for ln in transfer.lines
    )
    old_status = transfer.status.value
    if fully_received:
        transfer.status = StockTransferStatus.RECEIVED
        transfer.actual_arrival_date = _utc_naive().date()
        await event_bus.publish(
            DocumentStatusChanged(
                document_type="TRANSFER",
                document_id=transfer.id,
                document_no=transfer.document_no,
                old_status=old_status,
                new_status=StockTransferStatus.RECEIVED.value,
                organization_id=org_id,
                actor_user_id=user.id,
            ),
            session,
        )

    transfer.updated_by = user.id
    session.add(transfer)
    await session.flush()
    transfer = await repo.get_detail(org_id, transfer_id)  # type: ignore[assignment]
    logger.info(
        "stock_transfer_received",
        transfer_id=transfer_id,
        document_no=transfer.document_no,  # type: ignore[union-attr]
        fully_received=fully_received,
    )
    return _to_response(transfer)  # type: ignore[arg-type]


async def cancel_transfer(
    session: AsyncSession,
    transfer_id: int,
    data: StockTransferCancel,
    *,
    org_id: int,
    user: User,
) -> StockTransferDetail:
    """Cancel a transfer.

    DRAFT → CANCELLED       (any role with write permission)
    CONFIRMED → CANCELLED   (Manager / Admin only)
    IN_TRANSIT / RECEIVED → CANCELLED forbidden — goods are physically moving.
    """
    repo = StockTransferRepository(session)
    transfer = await repo.get_detail(org_id, transfer_id)
    if transfer is None:
        raise NotFoundError(message=f"Stock transfer {transfer_id} not found.")

    if transfer.status not in (
        StockTransferStatus.DRAFT,
        StockTransferStatus.CONFIRMED,
    ):
        raise InvalidStatusTransitionError(
            message=(
                f"Cannot cancel a stock transfer in {transfer.status.value} status."
            )
        )

    if transfer.status == StockTransferStatus.CONFIRMED and not _user_has_role(
        user, RoleCode.ADMIN, RoleCode.MANAGER
    ):
        raise AuthorizationError(
            message="Only Manager or Admin can cancel a confirmed stock transfer."
        )

    old_status = transfer.status.value
    transfer.status = StockTransferStatus.CANCELLED
    transfer.remarks = (transfer.remarks or "") + f"\n[CANCELLED] {data.cancel_reason}"
    transfer.updated_by = user.id
    session.add(transfer)

    await event_bus.publish(
        DocumentStatusChanged(
            document_type="TRANSFER",
            document_id=transfer.id,
            document_no=transfer.document_no,
            old_status=old_status,
            new_status=StockTransferStatus.CANCELLED.value,
            organization_id=org_id,
            actor_user_id=user.id,
        ),
        session,
    )

    await session.flush()
    transfer = await repo.get_detail(org_id, transfer_id)  # type: ignore[assignment]
    logger.info(
        "stock_transfer_cancelled",
        transfer_id=transfer_id,
        reason=data.cancel_reason,
    )
    return _to_response(transfer)  # type: ignore[arg-type]
