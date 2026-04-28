"""Unit tests for GoodsReceipt service (Window 8).

Coverage:
* Happy path: PO CONFIRMED → create GR → on_hand/incoming/avg_cost updated.
* PO state transitions:
    - partial receive → PO becomes PARTIAL_RECEIVED
    - full receive    → PO becomes FULLY_RECEIVED
* Status guards: cannot receive on DRAFT / CANCELLED PO.
* Validation: PO line not in this PO; duplicate PO line.
* Over-receipt tolerance (env-driven, default 5%):
    - within tolerance → accepted
    - exactly at tolerance boundary → accepted
    - beyond tolerance → BusinessRuleError(GR_OVER_RECEIPT_EXCEEDED)
    - tolerance=0 (strict) → any over-receipt rejected
* Already-fully-received line → BusinessRuleError(GR_LINE_ALREADY_FULL).

All tests mock the DB session and inventory.apply_purchase_in to keep the
focus on orchestration logic.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import (
    BusinessRuleError,
    InvalidStatusTransitionError,
    NotFoundError,
    ValidationError,
)
from app.enums import POStatus, RoleCode
from app.schemas.goods_receipt import GoodsReceiptCreate, GoodsReceiptLineCreate
from app.services import goods_receipt as gr_service
from tests.conftest import make_mock_session, make_mock_user


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_po_line(
    line_id: int = 101,
    qty_ordered: Decimal = Decimal("100"),
    qty_received: Decimal = Decimal("0"),
    sku_id: int = 11,
    line_no: int = 1,
) -> MagicMock:
    line = MagicMock()
    line.id = line_id
    line.line_no = line_no
    line.sku_id = sku_id
    line.uom_id = 1
    line.qty_ordered = qty_ordered
    line.qty_received = qty_received
    line.unit_price_excl_tax = Decimal("10.0000")
    return line


def _make_po(
    *,
    status: POStatus = POStatus.CONFIRMED,
    lines: list[MagicMock] | None = None,
) -> MagicMock:
    po = MagicMock()
    po.id = 555
    po.organization_id = 1
    po.document_no = "PO-2026-00001"
    po.status = status
    po.warehouse_id = 21
    po.lines = lines if lines is not None else [_make_po_line()]
    po.updated_by = None
    return po


def _make_gr_after_create() -> MagicMock:
    """Mock GR returned by repo.get_detail after creation."""
    gr = MagicMock()
    gr.id = 7
    gr.organization_id = 1
    gr.document_no = "GR-2026-00001"
    gr.purchase_order_id = 555
    gr.warehouse_id = 21
    gr.receipt_date = date(2026, 4, 28)
    gr.delivery_note_no = None
    gr.received_by = 1
    gr.created_by = 1
    gr.remarks = None
    gr.lines = []
    gr.purchase_order = MagicMock()
    gr.purchase_order.document_no = "PO-2026-00001"
    gr.created_at = MagicMock()
    gr.updated_at = MagicMock()
    return gr


def _patch_common(po: MagicMock, gr_full: MagicMock | None = None):
    """Return a context-manager dict that mocks all external collaborators."""
    if gr_full is None:
        gr_full = _make_gr_after_create()

    po_repo = MagicMock()
    po_repo.get_detail = AsyncMock(return_value=po)
    gr_repo = MagicMock()
    gr_repo.get_detail = AsyncMock(return_value=gr_full)

    return {
        "po_repo": patch(
            "app.services.goods_receipt.PurchaseOrderRepository",
            return_value=po_repo,
        ),
        "gr_repo": patch(
            "app.services.goods_receipt.GoodsReceiptRepository",
            return_value=gr_repo,
        ),
        "next_doc_no": patch(
            "app.services.goods_receipt.next_document_no",
            new=AsyncMock(return_value="GR-2026-00001"),
        ),
        "apply": patch(
            "app.services.goods_receipt.inventory_svc.apply_purchase_in",
            new=AsyncMock(return_value=(MagicMock(), Decimal("12.0000"))),
        ),
        "publish": patch(
            "app.services.goods_receipt.event_bus.publish",
            new=AsyncMock(),
        ),
        "to_response": patch(
            "app.services.goods_receipt._to_response",
            return_value=MagicMock(),
        ),
    }


def _build_gr_input(
    po_line_id: int = 101,
    qty: Decimal = Decimal("60"),
    unit_cost: Decimal | None = None,
) -> GoodsReceiptCreate:
    return GoodsReceiptCreate(
        purchase_order_id=555,
        receipt_date=date(2026, 4, 28),
        lines=[
            GoodsReceiptLineCreate(
                purchase_order_line_id=po_line_id,
                qty_received=qty,
                unit_cost=unit_cost,
            )
        ],
    )


# ── Happy path + PO status transitions ───────────────────────────────────────


@pytest.mark.asyncio
class TestPOStatusTransition:
    async def test_partial_receive_advances_po_to_partial_received(self) -> None:
        po_line = _make_po_line(qty_ordered=Decimal("100"), qty_received=Decimal("0"))
        po = _make_po(status=POStatus.CONFIRMED, lines=[po_line])
        user = make_mock_user(role=RoleCode.PURCHASER)
        session = make_mock_session()

        ctx = _patch_common(po)
        with (
            ctx["po_repo"], ctx["gr_repo"], ctx["next_doc_no"],
            ctx["apply"] as apply_mock, ctx["publish"], ctx["to_response"],
        ):
            await gr_service.create_gr(
                session,
                _build_gr_input(qty=Decimal("60")),
                org_id=1,
                user=user,
            )

        # PO line cumulative qty_received increased.
        assert po_line.qty_received == Decimal("60.0000")
        # PO transitioned to PARTIAL_RECEIVED.
        assert po.status == POStatus.PARTIAL_RECEIVED
        # apply_purchase_in invoked once with right args.
        apply_mock.assert_awaited_once()
        kwargs = apply_mock.await_args.kwargs
        assert kwargs["qty"] == Decimal("60.0000")
        assert kwargs["sku_id"] == 11
        assert kwargs["warehouse_id"] == 21

    async def test_full_receive_advances_po_to_fully_received(self) -> None:
        po_line = _make_po_line(qty_ordered=Decimal("100"), qty_received=Decimal("0"))
        po = _make_po(status=POStatus.CONFIRMED, lines=[po_line])
        user = make_mock_user(role=RoleCode.PURCHASER)
        session = make_mock_session()

        ctx = _patch_common(po)
        with (
            ctx["po_repo"], ctx["gr_repo"], ctx["next_doc_no"],
            ctx["apply"], ctx["publish"], ctx["to_response"],
        ):
            await gr_service.create_gr(
                session,
                _build_gr_input(qty=Decimal("100")),
                org_id=1,
                user=user,
            )

        assert po_line.qty_received == Decimal("100.0000")
        assert po.status == POStatus.FULLY_RECEIVED

    async def test_second_gr_completes_partial_to_fully(self) -> None:
        """PO already PARTIAL_RECEIVED with 60/100 → second GR receives 40."""
        po_line = _make_po_line(qty_ordered=Decimal("100"), qty_received=Decimal("60"))
        po = _make_po(status=POStatus.PARTIAL_RECEIVED, lines=[po_line])
        user = make_mock_user(role=RoleCode.PURCHASER)
        session = make_mock_session()

        ctx = _patch_common(po)
        with (
            ctx["po_repo"], ctx["gr_repo"], ctx["next_doc_no"],
            ctx["apply"], ctx["publish"], ctx["to_response"],
        ):
            await gr_service.create_gr(
                session,
                _build_gr_input(qty=Decimal("40")),
                org_id=1,
                user=user,
            )

        assert po_line.qty_received == Decimal("100.0000")
        assert po.status == POStatus.FULLY_RECEIVED


# ── Status guards ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestPOStatusGuards:
    @pytest.mark.parametrize(
        "status",
        [POStatus.DRAFT, POStatus.CANCELLED, POStatus.FULLY_RECEIVED],
    )
    async def test_non_receivable_status_rejected(self, status: POStatus) -> None:
        po = _make_po(status=status)
        user = make_mock_user(role=RoleCode.PURCHASER)
        session = make_mock_session()

        ctx = _patch_common(po)
        with ctx["po_repo"], ctx["gr_repo"], ctx["next_doc_no"]:
            with pytest.raises(InvalidStatusTransitionError) as exc:
                await gr_service.create_gr(
                    session, _build_gr_input(), org_id=1, user=user
                )
        assert exc.value.error_code == "PO_NOT_RECEIVABLE"

    async def test_po_not_found_raises(self) -> None:
        user = make_mock_user(role=RoleCode.PURCHASER)
        session = make_mock_session()
        po_repo = MagicMock()
        po_repo.get_detail = AsyncMock(return_value=None)

        with patch(
            "app.services.goods_receipt.PurchaseOrderRepository",
            return_value=po_repo,
        ):
            with pytest.raises(NotFoundError) as exc:
                await gr_service.create_gr(
                    session, _build_gr_input(), org_id=1, user=user
                )
        assert exc.value.error_code == "PO_NOT_FOUND"


# ── Input validation ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestInputValidation:
    async def test_po_line_id_not_in_po(self) -> None:
        po = _make_po()  # has line.id == 101
        user = make_mock_user(role=RoleCode.PURCHASER)
        session = make_mock_session()

        ctx = _patch_common(po)
        with ctx["po_repo"], ctx["gr_repo"]:
            with pytest.raises(ValidationError) as exc:
                await gr_service.create_gr(
                    session,
                    _build_gr_input(po_line_id=999),  # mismatch
                    org_id=1,
                    user=user,
                )
        assert exc.value.error_code == "GR_LINE_INVALID_PO_LINE"

    async def test_duplicate_po_line_in_input(self) -> None:
        po = _make_po()
        user = make_mock_user(role=RoleCode.PURCHASER)
        session = make_mock_session()

        data = GoodsReceiptCreate(
            purchase_order_id=555,
            receipt_date=date(2026, 4, 28),
            lines=[
                GoodsReceiptLineCreate(
                    purchase_order_line_id=101, qty_received=Decimal("50")
                ),
                GoodsReceiptLineCreate(
                    purchase_order_line_id=101, qty_received=Decimal("30")
                ),
            ],
        )

        ctx = _patch_common(po)
        with ctx["po_repo"], ctx["gr_repo"]:
            with pytest.raises(ValidationError) as exc:
                await gr_service.create_gr(session, data, org_id=1, user=user)
        assert exc.value.error_code == "GR_LINE_DUPLICATE"


# ── Over-receipt tolerance ───────────────────────────────────────────────────


@pytest.mark.asyncio
class TestOverReceiptTolerance:
    async def test_within_tolerance_accepted(self, monkeypatch) -> None:
        """qty_received = 104 (4% over 100) within default 5% tolerance."""
        from app.services import goods_receipt as gr_mod

        monkeypatch.setattr(gr_mod.settings, "GR_OVER_RECEIPT_TOLERANCE", Decimal("0.05"))
        po_line = _make_po_line(qty_ordered=Decimal("100"), qty_received=Decimal("0"))
        po = _make_po(status=POStatus.CONFIRMED, lines=[po_line])
        user = make_mock_user(role=RoleCode.PURCHASER)
        session = make_mock_session()

        ctx = _patch_common(po)
        with (
            ctx["po_repo"], ctx["gr_repo"], ctx["next_doc_no"],
            ctx["apply"], ctx["publish"], ctx["to_response"],
        ):
            # Should not raise.
            await gr_service.create_gr(
                session,
                _build_gr_input(qty=Decimal("104")),
                org_id=1,
                user=user,
            )

        # PO line accumulated past qty_ordered (allowed within tolerance).
        assert po_line.qty_received == Decimal("104.0000")
        # over qty_ordered → still flips PO to FULLY_RECEIVED (>= ordered).
        assert po.status == POStatus.FULLY_RECEIVED

    async def test_at_tolerance_boundary_accepted(self, monkeypatch) -> None:
        """qty_received exactly at 105 (5% over 100) is accepted."""
        from app.services import goods_receipt as gr_mod

        monkeypatch.setattr(gr_mod.settings, "GR_OVER_RECEIPT_TOLERANCE", Decimal("0.05"))
        po_line = _make_po_line(qty_ordered=Decimal("100"), qty_received=Decimal("0"))
        po = _make_po(status=POStatus.CONFIRMED, lines=[po_line])
        user = make_mock_user(role=RoleCode.PURCHASER)
        session = make_mock_session()

        ctx = _patch_common(po)
        with (
            ctx["po_repo"], ctx["gr_repo"], ctx["next_doc_no"],
            ctx["apply"], ctx["publish"], ctx["to_response"],
        ):
            await gr_service.create_gr(
                session,
                _build_gr_input(qty=Decimal("105")),
                org_id=1,
                user=user,
            )

        assert po_line.qty_received == Decimal("105.0000")

    async def test_beyond_tolerance_rejected(self, monkeypatch) -> None:
        """qty_received = 106 (6% over 100) exceeds 5% tolerance → 422."""
        from app.services import goods_receipt as gr_mod

        monkeypatch.setattr(gr_mod.settings, "GR_OVER_RECEIPT_TOLERANCE", Decimal("0.05"))
        po_line = _make_po_line(qty_ordered=Decimal("100"), qty_received=Decimal("0"))
        po = _make_po(status=POStatus.CONFIRMED, lines=[po_line])
        user = make_mock_user(role=RoleCode.PURCHASER)
        session = make_mock_session()

        ctx = _patch_common(po)
        with ctx["po_repo"], ctx["gr_repo"]:
            with pytest.raises(BusinessRuleError) as exc:
                await gr_service.create_gr(
                    session,
                    _build_gr_input(qty=Decimal("106")),
                    org_id=1,
                    user=user,
                )
        assert exc.value.error_code == "GR_OVER_RECEIPT_EXCEEDED"
        # Stock not touched, PO line unchanged.
        assert po_line.qty_received == Decimal("0")

    async def test_strict_mode_rejects_any_over_receipt(self, monkeypatch) -> None:
        """With tolerance=0, even 100.0001 over 100 is rejected."""
        from app.services import goods_receipt as gr_mod

        monkeypatch.setattr(gr_mod.settings, "GR_OVER_RECEIPT_TOLERANCE", Decimal("0"))
        po_line = _make_po_line(qty_ordered=Decimal("100"), qty_received=Decimal("0"))
        po = _make_po(status=POStatus.CONFIRMED, lines=[po_line])
        user = make_mock_user(role=RoleCode.PURCHASER)
        session = make_mock_session()

        ctx = _patch_common(po)
        with ctx["po_repo"], ctx["gr_repo"]:
            with pytest.raises(BusinessRuleError) as exc:
                await gr_service.create_gr(
                    session,
                    _build_gr_input(qty=Decimal("100.0001")),
                    org_id=1,
                    user=user,
                )
        assert exc.value.error_code == "GR_OVER_RECEIPT_EXCEEDED"

    async def test_strict_mode_accepts_exact_match(self, monkeypatch) -> None:
        """tolerance=0 still allows qty_received == remaining."""
        from app.services import goods_receipt as gr_mod

        monkeypatch.setattr(gr_mod.settings, "GR_OVER_RECEIPT_TOLERANCE", Decimal("0"))
        po_line = _make_po_line(qty_ordered=Decimal("100"), qty_received=Decimal("0"))
        po = _make_po(status=POStatus.CONFIRMED, lines=[po_line])
        user = make_mock_user(role=RoleCode.PURCHASER)
        session = make_mock_session()

        ctx = _patch_common(po)
        with (
            ctx["po_repo"], ctx["gr_repo"], ctx["next_doc_no"],
            ctx["apply"], ctx["publish"], ctx["to_response"],
        ):
            await gr_service.create_gr(
                session,
                _build_gr_input(qty=Decimal("100")),
                org_id=1,
                user=user,
            )
        assert po_line.qty_received == Decimal("100.0000")
        assert po.status == POStatus.FULLY_RECEIVED


# ── Already-fully-received guard ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_already_fully_received_line_rejected() -> None:
    """A second GR against a fully-received line is blocked."""
    po_line = _make_po_line(qty_ordered=Decimal("100"), qty_received=Decimal("100"))
    po = _make_po(status=POStatus.PARTIAL_RECEIVED, lines=[po_line])
    user = make_mock_user(role=RoleCode.PURCHASER)
    session = make_mock_session()

    ctx = _patch_common(po)
    with ctx["po_repo"], ctx["gr_repo"]:
        with pytest.raises(BusinessRuleError) as exc:
            await gr_service.create_gr(
                session,
                _build_gr_input(qty=Decimal("1")),
                org_id=1,
                user=user,
            )
    assert exc.value.error_code == "GR_LINE_ALREADY_FULL"


# ── Default unit_cost falls back to PO line price ────────────────────────────


@pytest.mark.asyncio
async def test_default_unit_cost_uses_po_line_price() -> None:
    """When GR line omits unit_cost, the PO line's unit_price_excl_tax is used."""
    po_line = _make_po_line(qty_ordered=Decimal("100"), qty_received=Decimal("0"))
    po_line.unit_price_excl_tax = Decimal("9.5000")
    po = _make_po(status=POStatus.CONFIRMED, lines=[po_line])
    user = make_mock_user(role=RoleCode.PURCHASER)
    session = make_mock_session()

    ctx = _patch_common(po)
    with (
        ctx["po_repo"], ctx["gr_repo"], ctx["next_doc_no"],
        ctx["apply"] as apply_mock, ctx["publish"], ctx["to_response"],
    ):
        await gr_service.create_gr(
            session,
            _build_gr_input(qty=Decimal("50"), unit_cost=None),
            org_id=1,
            user=user,
        )

    apply_mock.assert_awaited_once()
    assert apply_mock.await_args.kwargs["unit_cost"] == Decimal("9.5000")
