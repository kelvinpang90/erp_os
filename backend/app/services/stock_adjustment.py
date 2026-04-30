"""Stock Adjustment service — CRUD + 3-state state machine.

State machine (Window 13):
    DRAFT ──confirm (Manager/Admin)──▶ CONFIRMED   (terminal — applies inventory)
    DRAFT ──cancel──▶ CANCELLED

Each line carries qty_before and qty_after; qty_diff = qty_after - qty_before
is a DB-computed column. On confirm:
  * line.qty_diff > 0  → apply_adjustment_increase  (盘盈)
  * line.qty_diff < 0  → apply_adjustment_decrease  (盘亏)
  * line.qty_diff == 0 → skipped (no-op line, allowed for documentation only)

Permission: Manager/Admin only on confirm. Adjustments touch costs and could
hide shrinkage/theft if granted to operational roles.
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
)
from app.enums import RoleCode, StockAdjustmentStatus
from app.events import event_bus
from app.events.types import DocumentStatusChanged
from app.models.organization import User
from app.models.stock import StockAdjustment, StockAdjustmentLine
from app.repositories.stock_adjustment import StockAdjustmentRepository
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.stock_adjustment import (
    StockAdjustmentCancel,
    StockAdjustmentCreate,
    StockAdjustmentDetail,
    StockAdjustmentLineResponse,
    StockAdjustmentResponse,
    StockAdjustmentUpdate,
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


def _to_response(adj: StockAdjustment) -> StockAdjustmentDetail:
    lines = []
    for ln in adj.lines or []:
        resp = StockAdjustmentLineResponse.model_validate(ln)
        resp.sku_code = ln.sku.code if ln.sku else ""
        resp.sku_name = ln.sku.name if ln.sku else ""
        lines.append(resp)
    detail = StockAdjustmentDetail.model_validate(adj)
    detail.lines = lines
    detail.warehouse_name = adj.warehouse.name if adj.warehouse is not None else ""
    return detail


# ── Public API ────────────────────────────────────────────────────────────────


async def list_adjustments(
    session: AsyncSession,
    pagination: PaginationParams,
    *,
    org_id: int,
    status: StockAdjustmentStatus | None = None,
    warehouse_id: int | None = None,
    search: str | None = None,
) -> PaginatedResponse[StockAdjustmentResponse]:
    repo = StockAdjustmentRepository(session)
    items, total = await repo.list_with_filters(
        org_id,
        status=status,
        warehouse_id=warehouse_id,
        search=search,
        limit=pagination.page_size,
        offset=pagination.offset,
    )
    return PaginatedResponse[StockAdjustmentResponse].build(
        items=[StockAdjustmentResponse.model_validate(a) for a in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


async def get_adjustment(
    session: AsyncSession,
    adj_id: int,
    *,
    org_id: int,
) -> StockAdjustmentDetail:
    repo = StockAdjustmentRepository(session)
    adj = await repo.get_detail(org_id, adj_id)
    if adj is None:
        raise NotFoundError(message=f"Stock adjustment {adj_id} not found.")
    return _to_response(adj)


async def create_adjustment(
    session: AsyncSession,
    data: StockAdjustmentCreate,
    *,
    org_id: int,
    user: User,
) -> StockAdjustmentDetail:
    document_no = await next_document_no(session, "ADJ", org_id)

    adj = StockAdjustment(
        organization_id=org_id,
        document_no=document_no,
        status=StockAdjustmentStatus.DRAFT,
        warehouse_id=data.warehouse_id,
        business_date=data.business_date,
        reason=data.reason,
        reason_description=data.reason_description,
        remarks=data.remarks,
        created_by=user.id,
    )
    session.add(adj)
    await session.flush()

    for idx, ln in enumerate(data.lines):
        session.add(
            StockAdjustmentLine(
                stock_adjustment_id=adj.id,
                line_no=idx + 1,
                sku_id=ln.sku_id,
                uom_id=ln.uom_id,
                qty_before=ln.qty_before,
                qty_after=ln.qty_after,
                unit_cost=ln.unit_cost,
                batch_no=ln.batch_no,
                expiry_date=ln.expiry_date,
                notes=ln.notes,
            )
        )

    await session.flush()
    repo = StockAdjustmentRepository(session)
    adj = await repo.get_detail(org_id, adj.id)  # type: ignore[assignment]

    logger.info(
        "stock_adjustment_created",
        adj_id=adj.id,  # type: ignore[union-attr]
        document_no=adj.document_no,  # type: ignore[union-attr]
        org_id=org_id,
    )
    return _to_response(adj)  # type: ignore[arg-type]


async def update_adjustment(
    session: AsyncSession,
    adj_id: int,
    data: StockAdjustmentUpdate,
    *,
    org_id: int,
    user: User,
) -> StockAdjustmentDetail:
    repo = StockAdjustmentRepository(session)
    adj = await repo.get_detail(org_id, adj_id)
    if adj is None:
        raise NotFoundError(message=f"Stock adjustment {adj_id} not found.")
    if adj.status != StockAdjustmentStatus.DRAFT:
        raise BusinessRuleError(
            message="Only DRAFT stock adjustments can be edited.",
            error_code="ADJUSTMENT_NOT_EDITABLE",
        )

    if data.warehouse_id is not None:
        adj.warehouse_id = data.warehouse_id
    if data.business_date is not None:
        adj.business_date = data.business_date
    if data.reason is not None:
        adj.reason = data.reason
    if data.reason_description is not None:
        adj.reason_description = data.reason_description
    if data.remarks is not None:
        adj.remarks = data.remarks

    if data.lines is not None:
        for line in adj.lines:
            await session.delete(line)
        await session.flush()
        for idx, ln in enumerate(data.lines):
            session.add(
                StockAdjustmentLine(
                    stock_adjustment_id=adj.id,
                    line_no=idx + 1,
                    sku_id=ln.sku_id,
                    uom_id=ln.uom_id,
                    qty_before=ln.qty_before,
                    qty_after=ln.qty_after,
                    unit_cost=ln.unit_cost,
                    batch_no=ln.batch_no,
                    expiry_date=ln.expiry_date,
                    notes=ln.notes,
                )
            )

    session.add(adj)
    await session.flush()
    adj = await repo.get_detail(org_id, adj_id)  # type: ignore[assignment]
    return _to_response(adj)  # type: ignore[arg-type]


async def confirm_adjustment(
    session: AsyncSession,
    adj_id: int,
    *,
    org_id: int,
    user: User,
) -> StockAdjustmentDetail:
    """DRAFT → CONFIRMED. Apply per-line inventory delta. Manager/Admin only."""
    if not _user_has_role(user, RoleCode.ADMIN, RoleCode.MANAGER):
        raise AuthorizationError(
            message="Only Manager or Admin can confirm a stock adjustment."
        )

    repo = StockAdjustmentRepository(session)
    adj = await repo.get_detail(org_id, adj_id)
    if adj is None:
        raise NotFoundError(message=f"Stock adjustment {adj_id} not found.")
    if adj.status != StockAdjustmentStatus.DRAFT:
        raise InvalidStatusTransitionError(
            message=f"Cannot confirm a stock adjustment in {adj.status.value} status."
        )
    if not adj.lines:
        raise BusinessRuleError(
            message="Cannot confirm a stock adjustment with no lines.",
            error_code="ADJUSTMENT_NO_LINES",
        )

    for line in adj.lines:
        diff = (line.qty_after or Decimal("0")) - (line.qty_before or Decimal("0"))
        if diff > 0:
            await inventory_svc.apply_adjustment_increase(
                session,
                org_id=org_id,
                sku_id=line.sku_id,
                warehouse_id=adj.warehouse_id,
                qty=diff,
                unit_cost=line.unit_cost,
                source_document_id=adj.id,
                source_line_id=line.id,
                batch_no=line.batch_no,
                expiry_date=line.expiry_date,
                actor_user_id=user.id,
                notes=f"Adjustment {adj.document_no} ({adj.reason.value})",
            )
        elif diff < 0:
            await inventory_svc.apply_adjustment_decrease(
                session,
                org_id=org_id,
                sku_id=line.sku_id,
                warehouse_id=adj.warehouse_id,
                qty=-diff,
                source_document_id=adj.id,
                source_line_id=line.id,
                batch_no=line.batch_no,
                expiry_date=line.expiry_date,
                actor_user_id=user.id,
                notes=f"Adjustment {adj.document_no} ({adj.reason.value})",
            )
        # diff == 0: no-op, but the line stays for documentation.

    old_status = adj.status.value
    adj.status = StockAdjustmentStatus.CONFIRMED
    adj.approved_by = user.id
    adj.approved_at = _utc_naive()
    session.add(adj)

    await event_bus.publish(
        DocumentStatusChanged(
            document_type="ADJUSTMENT",
            document_id=adj.id,
            document_no=adj.document_no,
            old_status=old_status,
            new_status=StockAdjustmentStatus.CONFIRMED.value,
            organization_id=org_id,
            actor_user_id=user.id,
        ),
        session,
    )

    await session.flush()
    adj = await repo.get_detail(org_id, adj_id)  # type: ignore[assignment]
    logger.info(
        "stock_adjustment_confirmed",
        adj_id=adj_id,
        document_no=adj.document_no,  # type: ignore[union-attr]
    )
    return _to_response(adj)  # type: ignore[arg-type]


async def cancel_adjustment(
    session: AsyncSession,
    adj_id: int,
    data: StockAdjustmentCancel,
    *,
    org_id: int,
    user: User,
) -> StockAdjustmentDetail:
    """Cancel a DRAFT adjustment. CONFIRMED is terminal (irreversible)."""
    repo = StockAdjustmentRepository(session)
    adj = await repo.get_detail(org_id, adj_id)
    if adj is None:
        raise NotFoundError(message=f"Stock adjustment {adj_id} not found.")
    if adj.status != StockAdjustmentStatus.DRAFT:
        raise InvalidStatusTransitionError(
            message=f"Cannot cancel a stock adjustment in {adj.status.value} status."
        )

    old_status = adj.status.value
    adj.status = StockAdjustmentStatus.CANCELLED
    adj.remarks = (adj.remarks or "") + f"\n[CANCELLED] {data.cancel_reason}"
    session.add(adj)

    await event_bus.publish(
        DocumentStatusChanged(
            document_type="ADJUSTMENT",
            document_id=adj.id,
            document_no=adj.document_no,
            old_status=old_status,
            new_status=StockAdjustmentStatus.CANCELLED.value,
            organization_id=org_id,
            actor_user_id=user.id,
        ),
        session,
    )

    await session.flush()
    adj = await repo.get_detail(org_id, adj_id)  # type: ignore[assignment]
    logger.info(
        "stock_adjustment_cancelled",
        adj_id=adj_id,
        reason=data.cancel_reason,
    )
    return _to_response(adj)  # type: ignore[arg-type]
