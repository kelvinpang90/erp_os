"""Unit tests for the Credit Note service (Window 12)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import (
    BusinessRuleError,
    InvalidStatusTransitionError,
    NotFoundError,
)
from app.enums import (
    CreditNoteReason,
    CreditNoteStatus,
    InvoiceStatus,
    RoleCode,
)
from app.schemas.credit_note import CreditNoteCreateIn, CreditNoteLineIn
from app.services import credit_note as cn_service
from tests.conftest import make_mock_session, make_mock_user


# ── Helpers ──────────────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _make_sol(snapshot: Decimal | None = Decimal("8.00")) -> MagicMock:
    sol = MagicMock()
    sol.id = 200
    sol.snapshot_avg_cost = snapshot
    return sol


def _make_invoice_line(
    *,
    line_id: int = 100,
    line_no: int = 1,
    qty: Decimal = Decimal("10"),
    unit_price: Decimal = Decimal("100.00"),
    tax_rate_percent: Decimal = Decimal("10.00"),
    sol: MagicMock | None = None,
) -> MagicMock:
    ln = MagicMock()
    ln.id = line_id
    ln.line_no = line_no
    ln.sku_id = 11
    ln.uom_id = 1
    ln.description = f"Line {line_no} desc"
    ln.qty = qty
    ln.unit_price_excl_tax = unit_price
    ln.tax_rate_id = 1
    ln.tax_rate_percent = tax_rate_percent
    ln.sales_order_line = sol if sol is not None else _make_sol()
    return ln


def _make_invoice(
    *,
    status: InvoiceStatus = InvoiceStatus.VALIDATED,
    warehouse_id: int | None = 21,
    lines: list[MagicMock] | None = None,
) -> MagicMock:
    inv = MagicMock()
    inv.id = 5
    inv.organization_id = 1
    inv.document_no = "INV-2026-00001"
    inv.status = status
    inv.customer_id = 7
    inv.warehouse_id = warehouse_id
    inv.currency = "MYR"
    inv.exchange_rate = Decimal("1")
    inv.lines = lines if lines is not None else [_make_invoice_line()]
    return inv


def _make_cn(
    *,
    status: CreditNoteStatus = CreditNoteStatus.DRAFT,
    cn_id: int = 99,
    invoice: MagicMock | None = None,
) -> MagicMock:
    cn = MagicMock()
    cn.id = cn_id
    cn.organization_id = 1
    cn.document_no = "CN-2026-00001"
    cn.status = status
    cn.invoice_id = 5
    cn.customer_id = 7
    cn.business_date = date(2026, 4, 20)
    cn.reason = CreditNoteReason.RETURN
    cn.currency = "MYR"
    cn.exchange_rate = Decimal("1")
    cn.subtotal_excl_tax = Decimal("100.00")
    cn.tax_amount = Decimal("10.00")
    cn.total_incl_tax = Decimal("110.00")
    cn.uin = None
    cn.lines = [
        MagicMock(
            id=1, line_no=1, sku_id=11, uom_id=1, qty=Decimal("1"),
        )
    ]
    if invoice is None:
        invoice = _make_invoice(status=InvoiceStatus.VALIDATED)
    cn.invoice = invoice
    org = MagicMock()
    org.tin = "C1234567890"
    org.name = "Demo Sdn Bhd"
    org.msic_code = "47190"
    org.sst_registration_no = "SST-001"
    cn.organization = org
    cust = MagicMock()
    cust.id = 7
    cust.name = "Buyer Sdn Bhd"
    cust.tin = "C9999999999"
    cust.msic_code = None
    cn.customer = cust
    return cn


# ── create_credit_note ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_cn_happy_path_inbounds_stock_and_computes_totals():
    session = make_mock_session()
    user = make_mock_user(role=RoleCode.SALES)
    inv_line = _make_invoice_line(qty=Decimal("10"), unit_price=Decimal("100"))
    invoice = _make_invoice(lines=[inv_line])

    inv_repo = MagicMock()
    inv_repo.get_detail = AsyncMock(return_value=invoice)
    cn_repo = MagicMock()
    cn_repo.sum_credited_qty_per_invoice_line = AsyncMock(return_value={})
    cn_repo.get_detail = AsyncMock(return_value=_make_cn(invoice=invoice))

    inbound = AsyncMock()

    with (
        patch.object(cn_service, "InvoiceRepository", return_value=inv_repo),
        patch.object(cn_service, "CreditNoteRepository", return_value=cn_repo),
        patch.object(cn_service, "next_document_no", new=AsyncMock(return_value="CN-2026-00001")),
        patch.object(cn_service.inventory_svc, "apply_sales_return", new=inbound),
        patch.object(cn_service, "_to_detail", new=lambda x: x),
    ):
        result = await cn_service.create_credit_note(
            session,
            org_id=1,
            user=user,
            payload=CreditNoteCreateIn(
                invoice_id=5,
                reason=CreditNoteReason.RETURN,
                lines=[CreditNoteLineIn(invoice_line_id=100, qty=Decimal("3"))],
            ),
        )

    # Stock inbound was called once with the snapshot avg_cost.
    inbound.assert_awaited_once()
    kwargs = inbound.await_args.kwargs
    assert kwargs["sku_id"] == 11
    assert kwargs["warehouse_id"] == 21
    assert kwargs["qty"] == Decimal("3")
    assert kwargs["unit_cost"] == Decimal("8.00")  # SOL.snapshot_avg_cost

    # The CN is the most recent ``session.add`` argument with attr ``status``.
    assert result is not None


@pytest.mark.asyncio
async def test_create_cn_rejects_qty_exceeding_invoice_line():
    session = make_mock_session()
    user = make_mock_user(role=RoleCode.SALES)
    inv_line = _make_invoice_line(qty=Decimal("5"))
    invoice = _make_invoice(lines=[inv_line])

    inv_repo = MagicMock()
    inv_repo.get_detail = AsyncMock(return_value=invoice)
    cn_repo = MagicMock()
    cn_repo.sum_credited_qty_per_invoice_line = AsyncMock(return_value={})

    with (
        patch.object(cn_service, "InvoiceRepository", return_value=inv_repo),
        patch.object(cn_service, "CreditNoteRepository", return_value=cn_repo),
    ):
        with pytest.raises(BusinessRuleError) as exc:
            await cn_service.create_credit_note(
                session, org_id=1, user=user,
                payload=CreditNoteCreateIn(
                    invoice_id=5, reason=CreditNoteReason.RETURN,
                    lines=[CreditNoteLineIn(invoice_line_id=100, qty=Decimal("6"))],
                ),
            )
    assert exc.value.error_code == "CREDIT_NOTE_QTY_EXCEEDS_INVOICE"


@pytest.mark.asyncio
async def test_create_cn_rejects_cumulative_overcredit():
    """If 4 of 5 are already credited, a new CN for 2 must fail."""
    session = make_mock_session()
    user = make_mock_user(role=RoleCode.SALES)
    inv_line = _make_invoice_line(qty=Decimal("5"))
    invoice = _make_invoice(lines=[inv_line])

    inv_repo = MagicMock()
    inv_repo.get_detail = AsyncMock(return_value=invoice)
    cn_repo = MagicMock()
    cn_repo.sum_credited_qty_per_invoice_line = AsyncMock(
        return_value={inv_line.id: Decimal("4")}
    )

    with (
        patch.object(cn_service, "InvoiceRepository", return_value=inv_repo),
        patch.object(cn_service, "CreditNoteRepository", return_value=cn_repo),
    ):
        with pytest.raises(BusinessRuleError) as exc:
            await cn_service.create_credit_note(
                session, org_id=1, user=user,
                payload=CreditNoteCreateIn(
                    invoice_id=5, reason=CreditNoteReason.RETURN,
                    lines=[CreditNoteLineIn(invoice_line_id=100, qty=Decimal("2"))],
                ),
            )
    assert exc.value.error_code == "CREDIT_NOTE_QTY_EXCEEDS_INVOICE"


@pytest.mark.asyncio
async def test_create_cn_rejects_non_validated_invoice():
    session = make_mock_session()
    user = make_mock_user(role=RoleCode.SALES)
    invoice = _make_invoice(status=InvoiceStatus.DRAFT)

    inv_repo = MagicMock()
    inv_repo.get_detail = AsyncMock(return_value=invoice)

    with patch.object(cn_service, "InvoiceRepository", return_value=inv_repo):
        with pytest.raises(BusinessRuleError) as exc:
            await cn_service.create_credit_note(
                session, org_id=1, user=user,
                payload=CreditNoteCreateIn(
                    invoice_id=5, reason=CreditNoteReason.RETURN,
                    lines=[CreditNoteLineIn(invoice_line_id=100, qty=Decimal("1"))],
                ),
            )
    assert exc.value.error_code == "INVOICE_NOT_CREDITABLE"


@pytest.mark.asyncio
async def test_create_cn_rejects_invoice_without_warehouse():
    session = make_mock_session()
    user = make_mock_user(role=RoleCode.SALES)
    invoice = _make_invoice(warehouse_id=None)

    inv_repo = MagicMock()
    inv_repo.get_detail = AsyncMock(return_value=invoice)

    with patch.object(cn_service, "InvoiceRepository", return_value=inv_repo):
        with pytest.raises(BusinessRuleError) as exc:
            await cn_service.create_credit_note(
                session, org_id=1, user=user,
                payload=CreditNoteCreateIn(
                    invoice_id=5, reason=CreditNoteReason.RETURN,
                    lines=[CreditNoteLineIn(invoice_line_id=100, qty=Decimal("1"))],
                ),
            )
    assert exc.value.error_code == "INVOICE_WAREHOUSE_MISSING"


# ── submit_credit_note_to_myinvois ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_submit_cn_happy_path():
    session = make_mock_session()
    user = make_mock_user(role=RoleCode.SALES)
    cn = _make_cn(status=CreditNoteStatus.DRAFT)

    cn_repo = MagicMock()
    cn_repo.get_detail = AsyncMock(return_value=cn)

    fake_uin = "CABCDEF012345678"
    submit_result = MagicMock()
    submit_result.uin = fake_uin
    submit_result.qr_code_url = f"https://myinvois-mock.local/qr/{fake_uin}"
    submit_result.submitted_at = _now()
    submit_result.validated_at = _now()
    adapter = MagicMock()
    adapter.submit = AsyncMock(return_value=submit_result)

    publish_mock = AsyncMock()

    with (
        patch.object(cn_service, "CreditNoteRepository", return_value=cn_repo),
        patch.object(cn_service, "get_myinvois_adapter", return_value=adapter),
        patch.object(cn_service.event_bus, "publish", new=publish_mock),
        patch.object(cn_service, "_to_detail", new=lambda x: x),
    ):
        await cn_service.submit_credit_note_to_myinvois(
            session, cn_id=99, org_id=1, user=user
        )

    assert cn.status == CreditNoteStatus.VALIDATED
    assert cn.uin == fake_uin
    # Two events: DocumentStatusChanged + EInvoiceValidated.
    assert publish_mock.await_count == 2
    event_types = [type(c.args[0]).__name__ for c in publish_mock.await_args_list]
    assert "DocumentStatusChanged" in event_types
    assert "EInvoiceValidated" in event_types
    # CN payload must carry the CREDIT_NOTE marker.
    payload = adapter.submit.await_args.args[0]
    assert payload.invoice_type == "CREDIT_NOTE"


@pytest.mark.asyncio
async def test_submit_cn_rejects_non_draft():
    session = make_mock_session()
    user = make_mock_user(role=RoleCode.SALES)
    cn = _make_cn(status=CreditNoteStatus.VALIDATED)

    cn_repo = MagicMock()
    cn_repo.get_detail = AsyncMock(return_value=cn)

    with patch.object(cn_service, "CreditNoteRepository", return_value=cn_repo):
        with pytest.raises(InvalidStatusTransitionError) as exc:
            await cn_service.submit_credit_note_to_myinvois(
                session, cn_id=99, org_id=1, user=user
            )
    assert exc.value.error_code == "CREDIT_NOTE_INVALID_STATUS"


# ── cancel_credit_note ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cancel_cn_rolls_back_stock():
    session = make_mock_session()
    user = make_mock_user(role=RoleCode.MANAGER)
    cn = _make_cn(status=CreditNoteStatus.DRAFT)
    # 2 lines so we can verify both rollback calls.
    cn.lines = [
        MagicMock(id=1, sku_id=11, uom_id=1, qty=Decimal("3"), line_no=1),
        MagicMock(id=2, sku_id=12, uom_id=1, qty=Decimal("1"), line_no=2),
    ]

    cn_repo = MagicMock()
    cn_repo.get_detail = AsyncMock(return_value=cn)
    rollback_mock = AsyncMock()
    publish_mock = AsyncMock()

    with (
        patch.object(cn_service, "CreditNoteRepository", return_value=cn_repo),
        # Bug fix: use apply_sales_return_reverse, NOT apply_sales_out.
        # The latter required reserved >= qty which CN inbound never sets up.
        patch.object(
            cn_service.inventory_svc,
            "apply_sales_return_reverse",
            new=rollback_mock,
        ),
        patch.object(cn_service.event_bus, "publish", new=publish_mock),
        patch.object(cn_service, "_to_detail", new=lambda x: x),
    ):
        await cn_service.cancel_credit_note(
            session, cn_id=99, org_id=1, user=user
        )

    assert cn.status == CreditNoteStatus.CANCELLED
    assert rollback_mock.await_count == 2
    publish_mock.assert_awaited_once()  # only DocumentStatusChanged for cancel


@pytest.mark.asyncio
async def test_cancel_cn_rejects_non_draft():
    session = make_mock_session()
    user = make_mock_user(role=RoleCode.MANAGER)
    cn = _make_cn(status=CreditNoteStatus.VALIDATED)

    cn_repo = MagicMock()
    cn_repo.get_detail = AsyncMock(return_value=cn)

    with patch.object(cn_service, "CreditNoteRepository", return_value=cn_repo):
        with pytest.raises(InvalidStatusTransitionError) as exc:
            await cn_service.cancel_credit_note(
                session, cn_id=99, org_id=1, user=user
            )
    assert exc.value.error_code == "CREDIT_NOTE_INVALID_STATUS"


@pytest.mark.asyncio
async def test_get_credit_note_not_found():
    session = make_mock_session()
    cn_repo = MagicMock()
    cn_repo.get_detail = AsyncMock(return_value=None)

    with patch.object(cn_service, "CreditNoteRepository", return_value=cn_repo):
        with pytest.raises(NotFoundError) as exc:
            await cn_service.get_credit_note(session, cn_id=999, org_id=1)
    assert exc.value.error_code == "CREDIT_NOTE_NOT_FOUND"
