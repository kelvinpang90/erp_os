"""Unit tests for the e-Invoice service (Window 11).

Covers:
  1. get_finalize_window — DEMO_MODE on/off
  2. generate_draft_from_so — happy path, idempotency, status guards, no shipped qty
  3. submit_to_myinvois — happy path, status guard
  4. reject_by_buyer — within window, after window
  5. _lazy_finalize_if_due — transitions VALIDATED → FINAL after window
  6. run_finalize_scan — bulk finalize count
  7. notify_on_einvoice_validated handler — writes Notification row
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import (
    BusinessRuleError,
    InvalidStatusTransitionError,
)
from app.enums import (
    InvoiceStatus,
    InvoiceType,
    NotificationType,
    RejectedBy,
    RoleCode,
    SOStatus,
)
from app.events.types import EInvoiceValidated
from app.schemas.invoice import GenerateFromSOIn, RejectByBuyerIn
from app.services import einvoice as einvoice_service
from tests.conftest import make_mock_session, make_mock_user


# ── Helpers ──────────────────────────────────────────────────────────────────


def _now_utc() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _make_sku(sku_id: int = 10, code: str = "SKU-001", name: str = "Test SKU") -> MagicMock:
    sku = MagicMock()
    sku.id = sku_id
    sku.code = code
    sku.name = name
    sku.msic_code = "47190"
    return sku


def _make_uom(uom_id: int = 1, code: str = "PCS") -> MagicMock:
    uom = MagicMock()
    uom.id = uom_id
    uom.code = code
    return uom


def _make_so_line(
    line_id: int = 100,
    qty_ordered: Decimal = Decimal("5"),
    qty_shipped: Decimal = Decimal("5"),
) -> MagicMock:
    line = MagicMock()
    line.id = line_id
    line.line_no = 1
    line.sku_id = 10
    line.sku = _make_sku()
    line.description = "Test line"
    line.uom_id = 1
    line.qty_ordered = qty_ordered
    line.qty_shipped = qty_shipped
    line.qty_invoiced = Decimal("0")
    line.unit_price_excl_tax = Decimal("100.00")
    line.tax_rate_id = 1
    line.tax_rate_percent = Decimal("10.00")
    line.discount_amount = Decimal("0")
    return line


def _make_so(
    status: SOStatus = SOStatus.FULLY_SHIPPED,
    lines_count: int = 1,
    shipped_qty: Decimal = Decimal("5"),
) -> MagicMock:
    so = MagicMock()
    so.id = 1
    so.organization_id = 1
    so.document_no = "SO-2026-00001"
    so.status = status
    so.customer_id = 7
    so.warehouse_id = 1
    so.currency = "MYR"
    so.exchange_rate = Decimal("1")
    so.payment_terms_days = 30
    so.lines = [
        _make_so_line(line_id=100 + i, qty_shipped=shipped_qty)
        for i in range(lines_count)
    ]
    return so


def _make_invoice(
    status: InvoiceStatus = InvoiceStatus.DRAFT,
    validated_at: datetime | None = None,
    invoice_id: int = 5,
) -> MagicMock:
    inv = MagicMock()
    inv.id = invoice_id
    inv.organization_id = 1
    inv.document_no = "INV-2026-00001"
    inv.invoice_type = InvoiceType.INVOICE
    inv.status = status
    inv.sales_order_id = 1
    inv.customer_id = 7
    inv.warehouse_id = 1
    inv.business_date = _now_utc().date()
    inv.due_date = None
    inv.currency = "MYR"
    inv.exchange_rate = Decimal("1")
    inv.subtotal_excl_tax = Decimal("500.00")
    inv.tax_amount = Decimal("50.00")
    inv.discount_amount = Decimal("0")
    inv.total_incl_tax = Decimal("550.00")
    inv.base_currency_amount = Decimal("550.00")
    inv.paid_amount = Decimal("0")
    inv.uin = None
    inv.qr_code_url = None
    inv.submitted_at = None
    inv.validated_at = validated_at
    inv.finalized_at = None
    inv.rejected_at = None
    inv.rejected_by = None
    inv.rejection_reason = None
    inv.rejection_attachment_id = None
    inv.precheck_result = None
    inv.precheck_at = None
    inv.remarks = None
    inv.lines = []
    # Required for the response mapper
    org = MagicMock()
    org.tin = "C1234567890"
    org.name = "Demo Sdn Bhd"
    org.msic_code = "47190"
    org.sst_registration_no = "SST-12345"
    inv.organization = org
    cust = MagicMock()
    cust.id = 7
    cust.name = "Buyer Sdn Bhd"
    cust.tin = "C9999999999"
    cust.msic_code = None
    inv.customer = cust
    wh = MagicMock()
    wh.name = "Main Warehouse"
    inv.warehouse = wh
    so_ref = MagicMock()
    so_ref.document_no = "SO-2026-00001"
    inv.sales_order = so_ref
    return inv


# ── get_finalize_window ──────────────────────────────────────────────────────


def test_finalize_window_demo_mode():
    with patch.object(einvoice_service.settings, "DEMO_MODE", True):
        assert einvoice_service.get_finalize_window() == timedelta(seconds=72)


def test_finalize_window_prod_mode():
    with patch.object(einvoice_service.settings, "DEMO_MODE", False):
        assert einvoice_service.get_finalize_window() == timedelta(hours=72)


# ── generate_draft_from_so ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_draft_happy_path():
    session = make_mock_session()
    so = _make_so(status=SOStatus.FULLY_SHIPPED, lines_count=2, shipped_qty=Decimal("3"))
    inv = _make_invoice()
    user = make_mock_user(role=RoleCode.SALES)

    so_repo = MagicMock()
    so_repo.get_detail = AsyncMock(return_value=so)
    inv_repo = MagicMock()
    inv_repo.get_by_so_id = AsyncMock(return_value=None)
    inv_repo.get_detail = AsyncMock(return_value=inv)

    sentinel = MagicMock()
    sentinel.document_no = inv.document_no
    sentinel.id = inv.id
    with (
        patch("app.services.einvoice.SalesOrderRepository", return_value=so_repo),
        patch("app.services.einvoice.InvoiceRepository", return_value=inv_repo),
        patch(
            "app.services.einvoice.next_document_no",
            new=AsyncMock(return_value="INV-2026-00001"),
        ),
        patch("app.services.einvoice._to_detail", return_value=sentinel),
        patch(
            "app.services.einvoice._so_already_consolidated",
            new=AsyncMock(return_value=False),
        ),
    ):
        result = await einvoice_service.generate_draft_from_so(
            session,
            so_id=1,
            org_id=1,
            user=user,
            payload=GenerateFromSOIn(),
        )

    assert result.document_no == inv.document_no
    # SO line qty_invoiced should have been incremented for each shipped line.
    for ln in so.lines:
        assert ln.qty_invoiced == Decimal("3")


@pytest.mark.asyncio
async def test_generate_idempotent_returns_existing():
    """Second call returns existing invoice without creating a new one."""
    session = make_mock_session()
    so = _make_so()
    existing = _make_invoice(status=InvoiceStatus.DRAFT, invoice_id=42)
    user = make_mock_user(role=RoleCode.SALES)

    so_repo = MagicMock()
    so_repo.get_detail = AsyncMock(return_value=so)
    inv_repo = MagicMock()
    inv_repo.get_by_so_id = AsyncMock(return_value=existing)
    inv_repo.get_detail = AsyncMock(return_value=existing)
    seq_mock = AsyncMock()
    sentinel = MagicMock()
    sentinel.id = 42

    with (
        patch("app.services.einvoice.SalesOrderRepository", return_value=so_repo),
        patch("app.services.einvoice.InvoiceRepository", return_value=inv_repo),
        patch("app.services.einvoice.next_document_no", new=seq_mock),
        patch("app.services.einvoice._to_detail", return_value=sentinel),
    ):
        result = await einvoice_service.generate_draft_from_so(
            session, so_id=1, org_id=1, user=user, payload=GenerateFromSOIn()
        )

    assert result.id == 42
    seq_mock.assert_not_awaited()  # No new doc number issued.


@pytest.mark.asyncio
async def test_generate_rejects_unshipped_so():
    session = make_mock_session()
    so = _make_so(status=SOStatus.CONFIRMED)
    user = make_mock_user(role=RoleCode.SALES)

    so_repo = MagicMock()
    so_repo.get_detail = AsyncMock(return_value=so)

    with patch("app.services.einvoice.SalesOrderRepository", return_value=so_repo):
        with pytest.raises(BusinessRuleError) as exc:
            await einvoice_service.generate_draft_from_so(
                session, so_id=1, org_id=1, user=user, payload=GenerateFromSOIn()
            )
    assert exc.value.error_code == "SO_NOT_INVOICEABLE"


@pytest.mark.asyncio
async def test_generate_rejects_zero_shipped_lines():
    """SO PARTIAL_SHIPPED but every line has qty_shipped=0 should raise."""
    session = make_mock_session()
    so = _make_so(status=SOStatus.PARTIAL_SHIPPED, shipped_qty=Decimal("0"))
    user = make_mock_user(role=RoleCode.SALES)

    so_repo = MagicMock()
    so_repo.get_detail = AsyncMock(return_value=so)
    inv_repo = MagicMock()
    inv_repo.get_by_so_id = AsyncMock(return_value=None)

    with (
        patch("app.services.einvoice.SalesOrderRepository", return_value=so_repo),
        patch("app.services.einvoice.InvoiceRepository", return_value=inv_repo),
        patch(
            "app.services.einvoice._so_already_consolidated",
            new=AsyncMock(return_value=False),
        ),
    ):
        with pytest.raises(BusinessRuleError) as exc:
            await einvoice_service.generate_draft_from_so(
                session, so_id=1, org_id=1, user=user, payload=GenerateFromSOIn()
            )
    assert exc.value.error_code == "SO_NOTHING_SHIPPED"


# ── submit_to_myinvois ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_submit_draft_to_validated_happy_path():
    session = make_mock_session()
    inv = _make_invoice(status=InvoiceStatus.DRAFT)
    user = make_mock_user(role=RoleCode.SALES)

    inv_repo = MagicMock()
    inv_repo.get_detail = AsyncMock(return_value=inv)

    fake_uin = "ABCDEF0123456789"
    submit_result = MagicMock()
    submit_result.uin = fake_uin
    submit_result.qr_code_url = f"https://myinvois-mock.local/qr/{fake_uin}"
    submit_result.submitted_at = _now_utc()
    submit_result.validated_at = _now_utc()

    adapter = MagicMock()
    adapter.submit = AsyncMock(return_value=submit_result)

    publish_mock = AsyncMock()

    sentinel = MagicMock()
    sentinel.uin = fake_uin

    with (
        patch("app.services.einvoice.InvoiceRepository", return_value=inv_repo),
        patch("app.services.einvoice.get_myinvois_adapter", return_value=adapter),
        patch("app.services.einvoice.event_bus.publish", new=publish_mock),
        patch("app.services.einvoice._to_detail", return_value=sentinel),
    ):
        result = await einvoice_service.submit_to_myinvois(
            session, invoice_id=5, org_id=1, user=user
        )

    assert inv.status == InvoiceStatus.VALIDATED
    assert inv.uin == fake_uin
    assert inv.qr_code_url == submit_result.qr_code_url
    assert inv.submitted_at is not None
    assert inv.validated_at is not None
    assert result.uin == fake_uin

    # Two events published: DocumentStatusChanged + EInvoiceValidated.
    assert publish_mock.await_count == 2
    event_types = [type(call.args[0]).__name__ for call in publish_mock.await_args_list]
    assert "DocumentStatusChanged" in event_types
    assert "EInvoiceValidated" in event_types


@pytest.mark.asyncio
async def test_submit_rejects_non_draft():
    session = make_mock_session()
    inv = _make_invoice(status=InvoiceStatus.VALIDATED, validated_at=_now_utc())
    user = make_mock_user(role=RoleCode.SALES)

    inv_repo = MagicMock()
    inv_repo.get_detail = AsyncMock(return_value=inv)

    with patch("app.services.einvoice.InvoiceRepository", return_value=inv_repo):
        with pytest.raises(InvalidStatusTransitionError) as exc:
            await einvoice_service.submit_to_myinvois(
                session, invoice_id=5, org_id=1, user=user
            )
    assert exc.value.error_code == "INVOICE_INVALID_STATUS"


# ── reject_by_buyer ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reject_within_window_demo_mode():
    """DEMO_MODE: 30s elapsed (<72s) → reject succeeds."""
    session = make_mock_session()
    inv = _make_invoice(
        status=InvoiceStatus.VALIDATED,
        validated_at=_now_utc() - timedelta(seconds=30),
    )
    inv.uin = "DEADBEEF12345678"
    user = make_mock_user(role=RoleCode.MANAGER)

    inv_repo = MagicMock()
    inv_repo.get_detail = AsyncMock(return_value=inv)
    adapter = MagicMock()
    adapter.reject = AsyncMock()

    with (
        patch.object(einvoice_service.settings, "DEMO_MODE", True),
        patch("app.services.einvoice.InvoiceRepository", return_value=inv_repo),
        patch("app.services.einvoice.get_myinvois_adapter", return_value=adapter),
        patch("app.services.einvoice.event_bus.publish", new=AsyncMock()),
        patch("app.services.einvoice._to_detail", return_value=MagicMock()),
    ):
        await einvoice_service.reject_by_buyer(
            session,
            invoice_id=5,
            org_id=1,
            user=user,
            payload=RejectByBuyerIn(reason="Wrong amount on line 2"),
        )

    assert inv.status == InvoiceStatus.REJECTED
    assert inv.rejected_by == RejectedBy.BUYER
    assert inv.rejection_reason == "Wrong amount on line 2"
    adapter.reject.assert_awaited_once()


@pytest.mark.asyncio
async def test_reject_after_window():
    """DEMO_MODE: 80s elapsed (>72s) → reject raises BusinessRuleError."""
    session = make_mock_session()
    inv = _make_invoice(
        status=InvoiceStatus.VALIDATED,
        validated_at=_now_utc() - timedelta(seconds=80),
    )
    user = make_mock_user(role=RoleCode.MANAGER)

    inv_repo = MagicMock()
    inv_repo.get_detail = AsyncMock(return_value=inv)

    with (
        patch.object(einvoice_service.settings, "DEMO_MODE", True),
        patch("app.services.einvoice.InvoiceRepository", return_value=inv_repo),
    ):
        with pytest.raises(BusinessRuleError) as exc:
            await einvoice_service.reject_by_buyer(
                session,
                invoice_id=5,
                org_id=1,
                user=user,
                payload=RejectByBuyerIn(reason="late"),
            )
    assert exc.value.error_code == "INVOICE_REJECTION_WINDOW_EXPIRED"
    # Status unchanged.
    assert inv.status == InvoiceStatus.VALIDATED


# ── _lazy_finalize_if_due ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lazy_finalize_transitions_after_window():
    session = make_mock_session()
    inv = _make_invoice(
        status=InvoiceStatus.VALIDATED,
        validated_at=_now_utc() - timedelta(seconds=200),
    )
    publish_mock = AsyncMock()

    with (
        patch.object(einvoice_service.settings, "DEMO_MODE", True),
        patch("app.services.einvoice.event_bus.publish", new=publish_mock),
    ):
        result = await einvoice_service._lazy_finalize_if_due(session, inv, actor_user_id=1)

    assert result.status == InvoiceStatus.FINAL
    assert result.finalized_at is not None
    publish_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_lazy_finalize_noop_within_window():
    session = make_mock_session()
    inv = _make_invoice(
        status=InvoiceStatus.VALIDATED,
        validated_at=_now_utc() - timedelta(seconds=10),
    )
    publish_mock = AsyncMock()

    with (
        patch.object(einvoice_service.settings, "DEMO_MODE", True),
        patch("app.services.einvoice.event_bus.publish", new=publish_mock),
    ):
        result = await einvoice_service._lazy_finalize_if_due(session, inv)

    assert result.status == InvoiceStatus.VALIDATED
    publish_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_lazy_finalize_skips_non_validated():
    """DRAFT / FINAL / REJECTED are unchanged by lazy finalize."""
    session = make_mock_session()
    for st in (InvoiceStatus.DRAFT, InvoiceStatus.FINAL, InvoiceStatus.REJECTED):
        inv = _make_invoice(status=st, validated_at=_now_utc() - timedelta(days=1))
        with patch("app.services.einvoice.event_bus.publish", new=AsyncMock()):
            result = await einvoice_service._lazy_finalize_if_due(session, inv)
        assert result.status == st


# ── run_finalize_scan ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_finalize_scan_returns_count_and_publishes_when_nonzero():
    session = make_mock_session()
    user = make_mock_user(role=RoleCode.ADMIN)

    inv_repo = MagicMock()
    inv_repo.bulk_finalize = AsyncMock(return_value=3)
    publish_mock = AsyncMock()

    with (
        patch.object(einvoice_service.settings, "DEMO_MODE", True),
        patch("app.services.einvoice.InvoiceRepository", return_value=inv_repo),
        patch("app.services.einvoice.event_bus.publish", new=publish_mock),
    ):
        result = await einvoice_service.run_finalize_scan(session, org_id=1, user=user)

    assert result.finalized_count == 3
    assert result.finalize_window_seconds == 72
    publish_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_finalize_scan_no_event_when_zero():
    session = make_mock_session()
    user = make_mock_user(role=RoleCode.ADMIN)

    inv_repo = MagicMock()
    inv_repo.bulk_finalize = AsyncMock(return_value=0)
    publish_mock = AsyncMock()

    with (
        patch("app.services.einvoice.InvoiceRepository", return_value=inv_repo),
        patch("app.services.einvoice.event_bus.publish", new=publish_mock),
    ):
        result = await einvoice_service.run_finalize_scan(session, org_id=1, user=user)

    assert result.finalized_count == 0
    publish_mock.assert_not_awaited()


# ── notification handler ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_notify_on_einvoice_validated_creates_notification():
    """Handler opens its own session and inserts a Notification row."""
    from app.events.handlers.notification import notify_on_einvoice_validated

    captured: list[object] = []

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        def add(self, obj):
            captured.append(obj)

        async def commit(self):
            pass

        async def rollback(self):
            pass

    with patch(
        "app.events.handlers.notification.AsyncSessionLocal",
        return_value=_FakeSession(),
    ):
        await notify_on_einvoice_validated(
            EInvoiceValidated(
                organization_id=1,
                invoice_id=42,
                invoice_no="INV-2026-00042",
                uin="ABC123",
                validated_at="2026-04-29T10:00:00",
            )
        )

    assert len(captured) == 1
    notif = captured[0]
    assert notif.type == NotificationType.EINVOICE_VALIDATED
    assert notif.related_entity_id == 42
    assert notif.organization_id == 1
    assert "INV-2026-00042" in notif.title
