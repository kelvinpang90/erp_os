"""
Unit tests for Stock Adjustment service (Window 13).

Covered:
  1. confirm: Manager allowed (gain/loss/no-op routed correctly per line)
  2. confirm: Purchaser denied
  3. confirm: non-DRAFT raises InvalidStatusTransitionError
  4. confirm: empty lines raise BusinessRuleError
  5. cancel:  DRAFT → CANCELLED OK
  6. cancel:  CONFIRMED → InvalidStatusTransitionError (terminal)
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import (
    AuthorizationError,
    BusinessRuleError,
    InvalidStatusTransitionError,
)
from app.enums import RoleCode, StockAdjustmentReason, StockAdjustmentStatus
from app.schemas.stock_adjustment import StockAdjustmentCancel
from app.services import stock_adjustment as adjustment_service
from tests.conftest import make_mock_session, make_mock_user


def _make_line(
    line_id: int = 1,
    qty_before: str = "10",
    qty_after: str = "12",
    unit_cost: str | None = None,
) -> MagicMock:
    line = MagicMock()
    line.id = line_id
    line.line_no = line_id
    line.sku_id = 100
    line.uom_id = 1
    line.qty_before = Decimal(qty_before)
    line.qty_after = Decimal(qty_after)
    line.unit_cost = Decimal(unit_cost) if unit_cost else None
    line.batch_no = None
    line.expiry_date = None
    line.notes = None
    return line


def _make_adj(
    status: StockAdjustmentStatus,
    lines: list | None = None,
) -> MagicMock:
    adj = MagicMock()
    adj.id = 1
    adj.organization_id = 1
    adj.document_no = "ADJ-2026-00001"
    adj.status = status
    adj.warehouse_id = 1
    adj.reason = StockAdjustmentReason.PHYSICAL_COUNT
    adj.lines = lines if lines is not None else [_make_line()]
    adj.remarks = None
    adj.approved_by = None
    adj.approved_at = None
    return adj


def _make_repo(adj: MagicMock) -> MagicMock:
    repo = MagicMock()
    repo.get_detail = AsyncMock(return_value=adj)
    return repo


@pytest.mark.asyncio
async def test_confirm_routes_lines_by_diff_sign():
    """Manager confirm routes increase/decrease/skip per qty_diff sign."""
    session = make_mock_session()
    gain = _make_line(line_id=1, qty_before="10", qty_after="13", unit_cost="5.00")
    loss = _make_line(line_id=2, qty_before="8", qty_after="5")
    noop = _make_line(line_id=3, qty_before="4", qty_after="4")
    adj = _make_adj(
        StockAdjustmentStatus.DRAFT, lines=[gain, loss, noop]
    )
    user = make_mock_user(role=RoleCode.MANAGER)

    inc = AsyncMock(return_value=(MagicMock(), Decimal("5.00")))
    dec = AsyncMock(return_value=(MagicMock(), Decimal("5.00")))

    with (
        patch(
            "app.services.stock_adjustment.StockAdjustmentRepository",
            return_value=_make_repo(adj),
        ),
        patch(
            "app.services.stock_adjustment.inventory_svc.apply_adjustment_increase",
            inc,
        ),
        patch(
            "app.services.stock_adjustment.inventory_svc.apply_adjustment_decrease",
            dec,
        ),
        patch(
            "app.services.stock_adjustment.event_bus.publish",
            new_callable=AsyncMock,
        ),
        patch(
            "app.services.stock_adjustment._to_response",
            return_value=MagicMock(),
        ),
    ):
        await adjustment_service.confirm_adjustment(session, 1, org_id=1, user=user)

    assert adj.status == StockAdjustmentStatus.CONFIRMED
    assert inc.await_count == 1
    assert dec.await_count == 1
    # Verify that the qty passed is the absolute diff.
    assert inc.await_args.kwargs["qty"] == Decimal("3")
    assert dec.await_args.kwargs["qty"] == Decimal("3")
    assert adj.approved_by == user.id
    assert adj.approved_at is not None


@pytest.mark.asyncio
async def test_confirm_purchaser_denied():
    """Purchaser cannot confirm a stock adjustment."""
    session = make_mock_session()
    adj = _make_adj(StockAdjustmentStatus.DRAFT)
    user = make_mock_user(role=RoleCode.PURCHASER)

    # Repository is never called because role check happens first.
    with pytest.raises(AuthorizationError):
        await adjustment_service.confirm_adjustment(session, 1, org_id=1, user=user)


@pytest.mark.asyncio
async def test_confirm_already_confirmed_raises():
    """Cannot confirm a non-DRAFT adjustment."""
    session = make_mock_session()
    adj = _make_adj(StockAdjustmentStatus.CONFIRMED)
    user = make_mock_user(role=RoleCode.ADMIN)

    with patch(
        "app.services.stock_adjustment.StockAdjustmentRepository",
        return_value=_make_repo(adj),
    ):
        with pytest.raises(InvalidStatusTransitionError):
            await adjustment_service.confirm_adjustment(
                session, 1, org_id=1, user=user
            )


@pytest.mark.asyncio
async def test_confirm_no_lines_raises():
    """Cannot confirm an adjustment with zero lines."""
    session = make_mock_session()
    adj = _make_adj(StockAdjustmentStatus.DRAFT, lines=[])
    user = make_mock_user(role=RoleCode.ADMIN)

    with patch(
        "app.services.stock_adjustment.StockAdjustmentRepository",
        return_value=_make_repo(adj),
    ):
        with pytest.raises(BusinessRuleError):
            await adjustment_service.confirm_adjustment(
                session, 1, org_id=1, user=user
            )


@pytest.mark.asyncio
async def test_cancel_draft_succeeds():
    """DRAFT → CANCELLED is allowed."""
    session = make_mock_session()
    adj = _make_adj(StockAdjustmentStatus.DRAFT)
    user = make_mock_user(role=RoleCode.PURCHASER)
    data = StockAdjustmentCancel(cancel_reason="recount in progress")

    with (
        patch(
            "app.services.stock_adjustment.StockAdjustmentRepository",
            return_value=_make_repo(adj),
        ),
        patch(
            "app.services.stock_adjustment.event_bus.publish",
            new_callable=AsyncMock,
        ),
        patch(
            "app.services.stock_adjustment._to_response",
            return_value=MagicMock(),
        ),
    ):
        await adjustment_service.cancel_adjustment(
            session, 1, data, org_id=1, user=user
        )

    assert adj.status == StockAdjustmentStatus.CANCELLED


@pytest.mark.asyncio
async def test_cancel_confirmed_terminal():
    """CONFIRMED is terminal — cannot cancel."""
    session = make_mock_session()
    adj = _make_adj(StockAdjustmentStatus.CONFIRMED)
    user = make_mock_user(role=RoleCode.ADMIN)
    data = StockAdjustmentCancel(cancel_reason="oops")

    with patch(
        "app.services.stock_adjustment.StockAdjustmentRepository",
        return_value=_make_repo(adj),
    ):
        with pytest.raises(InvalidStatusTransitionError):
            await adjustment_service.cancel_adjustment(
                session, 1, data, org_id=1, user=user
            )
