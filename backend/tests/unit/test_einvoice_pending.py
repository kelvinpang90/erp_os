"""Unit tests for asynchronous LHDN validation handling.

The mock adapter validates in a single round-trip, but the real MyInvois API
does not: a submission can be accepted and stay unvalidated for a while. These
tests pin the resulting states.

Covers:
  1. submit_to_myinvois — validated_at None parks the invoice in SUBMITTED
     without announcing EInvoiceValidated
  2. refresh_status — SUBMITTED → VALIDATED / REJECTED / still pending, and the
     no-op path for other statuses
  3. run_pending_scan — counts, and one failure not aborting the batch
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.enums import InvoiceStatus, RejectedBy, RoleCode
from app.services import einvoice as einvoice_service
from tests.conftest import make_mock_session, make_mock_user


def _now_utc() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _make_invoice(
    *,
    status: InvoiceStatus = InvoiceStatus.SUBMITTED,
    uin: str | None = "UUID123",
    invoice_id: int = 5,
) -> MagicMock:
    inv = MagicMock()
    inv.id = invoice_id
    inv.organization_id = 1
    inv.document_no = f"INV-2026-{invoice_id:05d}"
    inv.status = status
    inv.uin = uin
    inv.qr_code_url = None
    inv.submitted_at = _now_utc()
    inv.validated_at = None
    inv.rejected_at = None
    inv.rejected_by = None
    inv.rejection_reason = None
    return inv


def _submit_result(*, validated: bool, uin: str = "UUID123") -> MagicMock:
    result = MagicMock()
    result.uin = uin
    result.qr_code_url = f"https://preprod.myinvois.hasil.gov.my/{uin}/share/L1"
    result.submitted_at = _now_utc()
    result.validated_at = _now_utc() if validated else None
    result.submission_uid = "SUB123"
    return result


def _status_result(status: str, *, reason: str | None = None, qr: str | None = None):
    result = MagicMock()
    result.uin = "UUID123"
    result.status = status
    result.validated_at = _now_utc() if status == "VALIDATED" else None
    result.rejection_reason = reason
    result.qr_code_url = qr
    return result


# ── 1. submit parks on SUBMITTED when validation is pending ──────────────────


@pytest.mark.asyncio
async def test_submit_parks_on_submitted_when_validation_pending():
    session = make_mock_session()
    inv = _make_invoice(status=InvoiceStatus.DRAFT, uin=None)
    user = make_mock_user(role=RoleCode.SALES)

    repo = MagicMock()
    repo.get_detail = AsyncMock(return_value=inv)
    adapter = MagicMock()
    adapter.submit = AsyncMock(return_value=_submit_result(validated=False))
    publish = AsyncMock()

    with (
        patch("app.services.einvoice.InvoiceRepository", return_value=repo),
        patch("app.services.einvoice.get_myinvois_adapter", return_value=adapter),
        patch("app.services.einvoice.event_bus.publish", new=publish),
        patch("app.services.einvoice._to_detail", return_value=MagicMock()),
    ):
        await einvoice_service.submit_to_myinvois(
            session, invoice_id=5, org_id=1, user=user
        )

    assert inv.status == InvoiceStatus.SUBMITTED
    # The UIN is recorded even though validation is pending — re-submitting
    # would trip LHDN's 10-minute duplicate check.
    assert inv.uin == "UUID123"
    assert inv.validated_at is None

    # Only the status change is announced; validation has not happened yet.
    assert publish.await_count == 1
    assert type(publish.await_args_list[0].args[0]).__name__ == "DocumentStatusChanged"


@pytest.mark.asyncio
async def test_submit_still_validates_in_one_pass_when_adapter_says_so():
    """Mock-adapter behaviour is unchanged — the demo path stays identical."""
    session = make_mock_session()
    inv = _make_invoice(status=InvoiceStatus.DRAFT, uin=None)
    user = make_mock_user(role=RoleCode.SALES)

    repo = MagicMock()
    repo.get_detail = AsyncMock(return_value=inv)
    adapter = MagicMock()
    adapter.submit = AsyncMock(return_value=_submit_result(validated=True))
    publish = AsyncMock()

    with (
        patch("app.services.einvoice.InvoiceRepository", return_value=repo),
        patch("app.services.einvoice.get_myinvois_adapter", return_value=adapter),
        patch("app.services.einvoice.event_bus.publish", new=publish),
        patch("app.services.einvoice._to_detail", return_value=MagicMock()),
    ):
        await einvoice_service.submit_to_myinvois(
            session, invoice_id=5, org_id=1, user=user
        )

    assert inv.status == InvoiceStatus.VALIDATED
    assert publish.await_count == 2


# ── 2. refresh_status ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_refresh_status_promotes_to_validated():
    session = make_mock_session()
    inv = _make_invoice()
    user = make_mock_user(role=RoleCode.SALES)

    repo = MagicMock()
    repo.get_detail = AsyncMock(return_value=inv)
    adapter = MagicMock()
    adapter.get_status = AsyncMock(
        return_value=_status_result("VALIDATED", qr="https://portal/UUID123/share/L1")
    )
    publish = AsyncMock()

    with (
        patch("app.services.einvoice.InvoiceRepository", return_value=repo),
        patch("app.services.einvoice.get_myinvois_adapter", return_value=adapter),
        patch("app.services.einvoice.event_bus.publish", new=publish),
        patch("app.services.einvoice._to_detail", return_value=MagicMock()),
    ):
        await einvoice_service.refresh_status(
            session, invoice_id=5, org_id=1, user=user
        )

    assert inv.status == InvoiceStatus.VALIDATED
    assert inv.validated_at is not None
    assert inv.qr_code_url == "https://portal/UUID123/share/L1"
    assert publish.await_count == 2       # status change + EInvoiceValidated


@pytest.mark.asyncio
async def test_refresh_status_records_lhdn_rejection():
    session = make_mock_session()
    inv = _make_invoice()
    user = make_mock_user(role=RoleCode.SALES)

    repo = MagicMock()
    repo.get_detail = AsyncMock(return_value=inv)
    adapter = MagicMock()
    adapter.get_status = AsyncMock(
        return_value=_status_result("REJECTED", reason="LHDN validation failed: TIN")
    )
    publish = AsyncMock()

    with (
        patch("app.services.einvoice.InvoiceRepository", return_value=repo),
        patch("app.services.einvoice.get_myinvois_adapter", return_value=adapter),
        patch("app.services.einvoice.event_bus.publish", new=publish),
        patch("app.services.einvoice._to_detail", return_value=MagicMock()),
    ):
        await einvoice_service.refresh_status(
            session, invoice_id=5, org_id=1, user=user
        )

    assert inv.status == InvoiceStatus.REJECTED
    assert inv.rejected_by == RejectedBy.LHDN
    assert inv.rejection_reason == "LHDN validation failed: TIN"
    # No EInvoiceValidated for a rejection.
    assert publish.await_count == 1


@pytest.mark.asyncio
async def test_refresh_status_leaves_still_pending_untouched():
    session = make_mock_session()
    inv = _make_invoice()
    user = make_mock_user(role=RoleCode.SALES)

    repo = MagicMock()
    repo.get_detail = AsyncMock(return_value=inv)
    adapter = MagicMock()
    adapter.get_status = AsyncMock(return_value=_status_result("SUBMITTED"))
    publish = AsyncMock()

    with (
        patch("app.services.einvoice.InvoiceRepository", return_value=repo),
        patch("app.services.einvoice.get_myinvois_adapter", return_value=adapter),
        patch("app.services.einvoice.event_bus.publish", new=publish),
        patch("app.services.einvoice._to_detail", return_value=MagicMock()),
    ):
        await einvoice_service.refresh_status(
            session, invoice_id=5, org_id=1, user=user
        )

    assert inv.status == InvoiceStatus.SUBMITTED
    assert publish.await_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,uin",
    [
        (InvoiceStatus.DRAFT, None),
        (InvoiceStatus.VALIDATED, "UUID123"),
        (InvoiceStatus.SUBMITTED, None),      # submitted but no UIN recorded
    ],
)
async def test_refresh_status_is_a_no_op_off_the_pending_path(status, uin):
    session = make_mock_session()
    inv = _make_invoice(status=status, uin=uin)
    user = make_mock_user(role=RoleCode.SALES)

    repo = MagicMock()
    repo.get_detail = AsyncMock(return_value=inv)
    adapter = MagicMock()
    adapter.get_status = AsyncMock()

    with (
        patch("app.services.einvoice.InvoiceRepository", return_value=repo),
        patch("app.services.einvoice.get_myinvois_adapter", return_value=adapter),
        patch(
            "app.services.einvoice._lazy_finalize_if_due",
            new=AsyncMock(return_value=inv),
        ),
        patch("app.services.einvoice._to_detail", return_value=MagicMock()),
    ):
        await einvoice_service.refresh_status(
            session, invoice_id=5, org_id=1, user=user
        )

    adapter.get_status.assert_not_awaited()
    assert inv.status == status


# ── 3. run_pending_scan ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pending_scan_counts_outcomes():
    session = make_mock_session()
    user = make_mock_user(role=RoleCode.ADMIN)
    pending = [_make_invoice(invoice_id=i) for i in (1, 2, 3)]

    repo = MagicMock()
    repo.list_pending_validation = AsyncMock(return_value=pending)

    outcomes = [
        MagicMock(status=InvoiceStatus.VALIDATED),
        MagicMock(status=InvoiceStatus.REJECTED),
        MagicMock(status=InvoiceStatus.SUBMITTED),
    ]
    with (
        patch("app.services.einvoice.InvoiceRepository", return_value=repo),
        patch(
            "app.services.einvoice.refresh_status",
            new=AsyncMock(side_effect=outcomes),
        ),
    ):
        result = await einvoice_service.run_pending_scan(session, org_id=1, user=user)

    assert result.scanned_count == 3
    assert result.validated_count == 1
    assert result.rejected_count == 1
    assert result.still_pending_count == 1


@pytest.mark.asyncio
async def test_pending_scan_survives_one_failure():
    """LHDN erroring on one invoice must not abandon the rest of the batch."""
    session = make_mock_session()
    user = make_mock_user(role=RoleCode.ADMIN)
    pending = [_make_invoice(invoice_id=i) for i in (1, 2)]

    repo = MagicMock()
    repo.list_pending_validation = AsyncMock(return_value=pending)

    with (
        patch("app.services.einvoice.InvoiceRepository", return_value=repo),
        patch(
            "app.services.einvoice.refresh_status",
            new=AsyncMock(
                side_effect=[
                    RuntimeError("LHDN down"),
                    MagicMock(status=InvoiceStatus.VALIDATED),
                ]
            ),
        ),
    ):
        result = await einvoice_service.run_pending_scan(session, org_id=1, user=user)

    assert result.scanned_count == 2
    assert result.validated_count == 1
    assert result.still_pending_count == 1


@pytest.mark.asyncio
async def test_pending_scan_with_nothing_pending():
    session = make_mock_session()
    user = make_mock_user(role=RoleCode.ADMIN)

    repo = MagicMock()
    repo.list_pending_validation = AsyncMock(return_value=[])

    with patch("app.services.einvoice.InvoiceRepository", return_value=repo):
        result = await einvoice_service.run_pending_scan(session, org_id=1, user=user)

    assert result.scanned_count == 0
    assert result.validated_count == 0
