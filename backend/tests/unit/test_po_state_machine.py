"""
Unit tests for PO state machine transitions.

Tests:
  1. confirm_po: DRAFT → CONFIRMED (happy path)
  2. confirm_po: non-DRAFT status → InvalidStatusTransitionError
  3. cancel_po: DRAFT → CANCELLED (any role)
  4. cancel_po: CONFIRMED → CANCELLED (Manager allowed)
  5. cancel_po: CONFIRMED → CANCELLED (Purchaser denied)
  6. cancel_po: FULLY_RECEIVED → error
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import AuthorizationError, InvalidStatusTransitionError
from app.enums import POStatus, RoleCode
from app.schemas.purchase_order import PurchaseOrderCancel
from app.services import purchase as purchase_service
from tests.conftest import make_mock_session, make_mock_user


def _make_po(status: POStatus, lines: int = 1) -> MagicMock:
    po = MagicMock()
    po.id = 1
    po.organization_id = 1
    po.document_no = "PO-2026-00001"
    po.status = status
    po.warehouse_id = 1
    po.lines = [_make_line() for _ in range(lines)]
    po.updated_by = None
    po.confirmed_at = None
    po.cancelled_at = None
    po.cancel_reason = None
    return po


def _make_line() -> MagicMock:
    line = MagicMock()
    line.sku_id = 10
    line.qty_ordered = Decimal("5")
    line.unit_price_excl_tax = Decimal("10.00")
    return line


def _make_repo(po: MagicMock) -> MagicMock:
    repo = MagicMock()
    repo.get_detail = AsyncMock(return_value=po)
    return repo


@pytest.mark.asyncio
async def test_confirm_draft_po_succeeds():
    """DRAFT → CONFIRMED is allowed."""
    session = make_mock_session()
    po = _make_po(POStatus.DRAFT)
    user = make_mock_user(role=RoleCode.PURCHASER)

    with (
        patch(
            "app.services.purchase.PurchaseOrderRepository",
            return_value=_make_repo(po),
        ),
        patch("app.services.purchase._adjust_incoming", new_callable=AsyncMock),
        patch("app.services.purchase.event_bus.publish", new_callable=AsyncMock),
        patch("app.services.purchase._to_response", return_value=MagicMock()),
    ):
        await purchase_service.confirm_po(session, 1, org_id=1, user=user)

    assert po.status == POStatus.CONFIRMED
    assert po.confirmed_at is not None


@pytest.mark.asyncio
async def test_confirm_already_confirmed_raises():
    """Cannot confirm a non-DRAFT PO."""
    session = make_mock_session()
    po = _make_po(POStatus.CONFIRMED)
    user = make_mock_user()

    with patch(
        "app.services.purchase.PurchaseOrderRepository",
        return_value=_make_repo(po),
    ):
        with pytest.raises(InvalidStatusTransitionError):
            await purchase_service.confirm_po(session, 1, org_id=1, user=user)


@pytest.mark.asyncio
async def test_cancel_draft_po_any_role():
    """DRAFT PO can be cancelled by Purchaser."""
    session = make_mock_session()
    po = _make_po(POStatus.DRAFT)
    user = make_mock_user(role=RoleCode.PURCHASER)
    data = PurchaseOrderCancel(cancel_reason="Changed mind")

    with (
        patch(
            "app.services.purchase.PurchaseOrderRepository",
            return_value=_make_repo(po),
        ),
        patch("app.services.purchase.event_bus.publish", new_callable=AsyncMock),
        patch("app.services.purchase._to_response", return_value=MagicMock()),
    ):
        await purchase_service.cancel_po(session, 1, data, org_id=1, user=user)

    assert po.status == POStatus.CANCELLED


@pytest.mark.asyncio
async def test_cancel_confirmed_po_manager_allowed():
    """CONFIRMED PO can be cancelled by Manager."""
    session = make_mock_session()
    po = _make_po(POStatus.CONFIRMED)
    user = make_mock_user(role=RoleCode.MANAGER)
    data = PurchaseOrderCancel(cancel_reason="Supplier issue")

    with (
        patch(
            "app.services.purchase.PurchaseOrderRepository",
            return_value=_make_repo(po),
        ),
        patch("app.services.purchase._adjust_incoming", new_callable=AsyncMock),
        patch("app.services.purchase.event_bus.publish", new_callable=AsyncMock),
        patch("app.services.purchase._to_response", return_value=MagicMock()),
    ):
        await purchase_service.cancel_po(session, 1, data, org_id=1, user=user)

    assert po.status == POStatus.CANCELLED


@pytest.mark.asyncio
async def test_cancel_confirmed_po_purchaser_denied():
    """Purchaser cannot cancel a CONFIRMED PO."""
    session = make_mock_session()
    po = _make_po(POStatus.CONFIRMED)
    user = make_mock_user(role=RoleCode.PURCHASER)
    data = PurchaseOrderCancel(cancel_reason="Test")

    with patch(
        "app.services.purchase.PurchaseOrderRepository",
        return_value=_make_repo(po),
    ):
        with pytest.raises(AuthorizationError):
            await purchase_service.cancel_po(session, 1, data, org_id=1, user=user)


@pytest.mark.asyncio
async def test_cancel_fully_received_raises():
    """FULLY_RECEIVED PO cannot be cancelled."""
    session = make_mock_session()
    po = _make_po(POStatus.FULLY_RECEIVED)
    user = make_mock_user(role=RoleCode.ADMIN)
    data = PurchaseOrderCancel(cancel_reason="Test")

    with patch(
        "app.services.purchase.PurchaseOrderRepository",
        return_value=_make_repo(po),
    ):
        with pytest.raises(InvalidStatusTransitionError):
            await purchase_service.cancel_po(session, 1, data, org_id=1, user=user)
