"""
Unit tests for Stock Transfer state machine (Window 13).

State machine transitions:
  1. confirm_transfer:  DRAFT → CONFIRMED (happy path)
  2. confirm_transfer:  IN_TRANSIT → InvalidStatusTransitionError
  3. ship_out_transfer: CONFIRMED → IN_TRANSIT (calls apply_transfer_ship_out
                        per line + writes unit_cost_snapshot)
  4. receive_transfer:  partial → stays IN_TRANSIT
  5. receive_transfer:  full → RECEIVED (sets actual_arrival_date)
  6. receive_transfer:  over-receive → BusinessRuleError
  7. cancel_transfer:   CONFIRMED → CANCELLED requires Manager (Purchaser denied)
  8. ValidationError when from_warehouse == to_warehouse
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import (
    AuthorizationError,
    BusinessRuleError,
    InvalidStatusTransitionError,
    ValidationError,
)
from app.enums import RoleCode, StockTransferStatus
from app.schemas.stock_transfer import (
    StockTransferCancel,
    StockTransferCreate,
    StockTransferLineCreate,
    StockTransferReceiveLine,
    StockTransferReceiveRequest,
)
from app.services import stock_transfer as transfer_service
from tests.conftest import make_mock_session, make_mock_user


def _make_line(
    line_id: int = 1,
    line_no: int = 1,
    qty_sent: str = "10",
    qty_received: str = "0",
    snapshot: str | None = None,
) -> MagicMock:
    line = MagicMock()
    line.id = line_id
    line.line_no = line_no
    line.sku_id = 100
    line.uom_id = 1
    line.qty_sent = Decimal(qty_sent)
    line.qty_received = Decimal(qty_received)
    line.unit_cost_snapshot = Decimal(snapshot) if snapshot is not None else None
    line.batch_no = None
    line.expiry_date = None
    return line


def _make_transfer(
    status: StockTransferStatus,
    lines: list | None = None,
) -> MagicMock:
    transfer = MagicMock()
    transfer.id = 1
    transfer.organization_id = 1
    transfer.document_no = "TR-2026-00001"
    transfer.status = status
    transfer.from_warehouse_id = 1
    transfer.to_warehouse_id = 2
    transfer.lines = lines if lines is not None else [_make_line()]
    transfer.remarks = None
    transfer.actual_arrival_date = None
    return transfer


def _make_repo(transfer: MagicMock) -> MagicMock:
    repo = MagicMock()
    repo.get_detail = AsyncMock(return_value=transfer)
    return repo


@pytest.mark.asyncio
async def test_confirm_draft_transfer_succeeds():
    """DRAFT → CONFIRMED is allowed; no inventory side-effects."""
    session = make_mock_session()
    transfer = _make_transfer(StockTransferStatus.DRAFT)
    user = make_mock_user(role=RoleCode.PURCHASER)

    with (
        patch(
            "app.services.stock_transfer.StockTransferRepository",
            return_value=_make_repo(transfer),
        ),
        patch(
            "app.services.stock_transfer.event_bus.publish",
            new_callable=AsyncMock,
        ),
        patch(
            "app.services.stock_transfer._to_response",
            return_value=MagicMock(),
        ),
    ):
        await transfer_service.confirm_transfer(session, 1, org_id=1, user=user)

    assert transfer.status == StockTransferStatus.CONFIRMED


@pytest.mark.asyncio
async def test_confirm_in_transit_raises():
    """Cannot confirm a transfer already past CONFIRMED."""
    session = make_mock_session()
    transfer = _make_transfer(StockTransferStatus.IN_TRANSIT)
    user = make_mock_user()

    with patch(
        "app.services.stock_transfer.StockTransferRepository",
        return_value=_make_repo(transfer),
    ):
        with pytest.raises(InvalidStatusTransitionError):
            await transfer_service.confirm_transfer(session, 1, org_id=1, user=user)


@pytest.mark.asyncio
async def test_ship_out_writes_unit_cost_snapshot_and_advances_status():
    """CONFIRMED → IN_TRANSIT calls apply_transfer_ship_out per line and writes snapshot."""
    session = make_mock_session()
    transfer = _make_transfer(StockTransferStatus.CONFIRMED)
    user = make_mock_user(role=RoleCode.PURCHASER)

    ship_out_mock = AsyncMock(
        return_value=(MagicMock(), MagicMock(), Decimal("12.50")),
    )

    with (
        patch(
            "app.services.stock_transfer.StockTransferRepository",
            return_value=_make_repo(transfer),
        ),
        patch(
            "app.services.stock_transfer.inventory_svc.apply_transfer_ship_out",
            ship_out_mock,
        ),
        patch(
            "app.services.stock_transfer.event_bus.publish",
            new_callable=AsyncMock,
        ),
        patch(
            "app.services.stock_transfer._to_response",
            return_value=MagicMock(),
        ),
    ):
        await transfer_service.ship_out_transfer(session, 1, org_id=1, user=user)

    assert transfer.status == StockTransferStatus.IN_TRANSIT
    assert ship_out_mock.await_count == len(transfer.lines)
    # Snapshot copied to each line.
    for ln in transfer.lines:
        assert ln.unit_cost_snapshot == Decimal("12.50")


@pytest.mark.asyncio
async def test_receive_partial_keeps_in_transit():
    """Receiving less than qty_sent on every line stays in IN_TRANSIT."""
    session = make_mock_session()
    line1 = _make_line(line_id=1, qty_sent="10", qty_received="0", snapshot="5.00")
    line2 = _make_line(line_id=2, qty_sent="5", qty_received="0", snapshot="3.00")
    transfer = _make_transfer(StockTransferStatus.IN_TRANSIT, lines=[line1, line2])
    user = make_mock_user(role=RoleCode.PURCHASER)
    payload = StockTransferReceiveRequest(
        lines=[
            StockTransferReceiveLine(line_id=1, qty_received=Decimal("4")),
            StockTransferReceiveLine(line_id=2, qty_received=Decimal("2")),
        ]
    )

    receive_mock = AsyncMock(return_value=(MagicMock(), Decimal("5.00")))

    with (
        patch(
            "app.services.stock_transfer.StockTransferRepository",
            return_value=_make_repo(transfer),
        ),
        patch(
            "app.services.stock_transfer.inventory_svc.apply_transfer_receive",
            receive_mock,
        ),
        patch(
            "app.services.stock_transfer.event_bus.publish",
            new_callable=AsyncMock,
        ),
        patch(
            "app.services.stock_transfer._to_response",
            return_value=MagicMock(),
        ),
    ):
        await transfer_service.receive_transfer(
            session, 1, payload, org_id=1, user=user
        )

    assert transfer.status == StockTransferStatus.IN_TRANSIT
    assert line1.qty_received == Decimal("4")
    assert line2.qty_received == Decimal("2")
    assert transfer.actual_arrival_date is None


@pytest.mark.asyncio
async def test_receive_full_advances_to_received():
    """Receiving the full remaining qty advances to RECEIVED + stamps date."""
    session = make_mock_session()
    line1 = _make_line(line_id=1, qty_sent="10", qty_received="6", snapshot="5.00")
    transfer = _make_transfer(StockTransferStatus.IN_TRANSIT, lines=[line1])
    user = make_mock_user(role=RoleCode.PURCHASER)
    payload = StockTransferReceiveRequest(
        lines=[StockTransferReceiveLine(line_id=1, qty_received=Decimal("4"))]
    )

    with (
        patch(
            "app.services.stock_transfer.StockTransferRepository",
            return_value=_make_repo(transfer),
        ),
        patch(
            "app.services.stock_transfer.inventory_svc.apply_transfer_receive",
            new_callable=AsyncMock,
        ),
        patch(
            "app.services.stock_transfer.event_bus.publish",
            new_callable=AsyncMock,
        ),
        patch(
            "app.services.stock_transfer._to_response",
            return_value=MagicMock(),
        ),
    ):
        await transfer_service.receive_transfer(
            session, 1, payload, org_id=1, user=user
        )

    assert transfer.status == StockTransferStatus.RECEIVED
    assert line1.qty_received == Decimal("10")
    assert transfer.actual_arrival_date is not None


@pytest.mark.asyncio
async def test_receive_over_qty_sent_raises():
    """Receiving more than qty_sent (cumulative) raises BusinessRuleError."""
    session = make_mock_session()
    line1 = _make_line(line_id=1, qty_sent="10", qty_received="6", snapshot="5.00")
    transfer = _make_transfer(StockTransferStatus.IN_TRANSIT, lines=[line1])
    user = make_mock_user(role=RoleCode.PURCHASER)
    payload = StockTransferReceiveRequest(
        lines=[StockTransferReceiveLine(line_id=1, qty_received=Decimal("5"))]
    )

    with (
        patch(
            "app.services.stock_transfer.StockTransferRepository",
            return_value=_make_repo(transfer),
        ),
        patch(
            "app.services.stock_transfer.inventory_svc.apply_transfer_receive",
            new_callable=AsyncMock,
        ),
    ):
        with pytest.raises(BusinessRuleError):
            await transfer_service.receive_transfer(
                session, 1, payload, org_id=1, user=user
            )


@pytest.mark.asyncio
async def test_cancel_confirmed_transfer_purchaser_denied():
    """Purchaser cannot cancel a CONFIRMED transfer."""
    session = make_mock_session()
    transfer = _make_transfer(StockTransferStatus.CONFIRMED)
    user = make_mock_user(role=RoleCode.PURCHASER)
    data = StockTransferCancel(cancel_reason="Test")

    with patch(
        "app.services.stock_transfer.StockTransferRepository",
        return_value=_make_repo(transfer),
    ):
        with pytest.raises(AuthorizationError):
            await transfer_service.cancel_transfer(
                session, 1, data, org_id=1, user=user
            )


@pytest.mark.asyncio
async def test_create_with_same_warehouse_raises():
    """from_warehouse == to_warehouse must fail validation in service layer."""
    session = make_mock_session()
    user = make_mock_user(role=RoleCode.PURCHASER)
    data = StockTransferCreate(
        from_warehouse_id=1,
        to_warehouse_id=1,
        business_date=date(2026, 4, 30),
        lines=[
            StockTransferLineCreate(
                sku_id=100,
                uom_id=1,
                qty_sent=Decimal("5"),
            )
        ],
    )

    with pytest.raises(ValidationError):
        await transfer_service.create_transfer(session, data, org_id=1, user=user)
