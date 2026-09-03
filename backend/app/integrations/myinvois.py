"""MyInvois adapter Protocol — stable contract for LHDN e-Invoice integration.

Two implementations satisfy this Protocol:

- ``myinvois_mock.MyInvoisMockAdapter`` — deterministic, offline, used for
  local dev / demo / tests. Returns a fake UIN and reports the invoice as
  validated in the same round-trip.
- ``myinvois_real.MyInvoisRealAdapter`` — talks to LHDN over HTTP (preprod or
  production): OAuth 2.0 client-credentials, UBL 2.1 JSON document, SHA-256
  hash + base64 envelope, then a bounded poll for the validation outcome.

The factory in ``myinvois_factory.py`` picks one based on ``MYINVOIS_MODE``.
Service-layer code depends only on this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional, Protocol


# ── Party / line DTOs ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PartyInfo:
    """Seller or buyer block of a MyInvois document.

    Mirrors the UBL ``AccountingSupplierParty`` / ``AccountingCustomerParty``
    aggregate. Values are snapshots taken when the invoice was issued — never
    read live from master data at submission time.
    """

    tin: str
    name: str
    registration_no: Optional[str] = None
    sst_no: Optional[str] = None
    msic_code: Optional[str] = None
    # MSIC industry description that accompanies the code in UBL. The ERP does
    # not store one today; the builder falls back to "NOT APPLICABLE".
    msic_description: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postcode: Optional[str] = None
    country: str = "MY"
    phone: Optional[str] = None
    email: Optional[str] = None


@dataclass(frozen=True)
class LinePayload:
    """One ``InvoiceLine`` of a MyInvois document."""

    line_no: int
    description: str
    qty: Decimal
    uom_code: str                     # local UOM code, mapped to UN/ECE Rec 20
    unit_price_excl_tax: Decimal
    tax_type: str                     # app.enums.TaxType value
    tax_rate_percent: Decimal
    tax_amount: Decimal
    line_total_excl_tax: Decimal
    discount_amount: Decimal = Decimal("0")
    classification_code: Optional[str] = None   # LHDN "CLASS" list


# ── Document DTOs ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class InvoicePayload:
    """Provider-agnostic invoice payload submitted to MyInvois.

    The flat ``seller_*`` / ``buyer_*`` fields are the shallow summary the mock
    adapter logs. The real adapter uses the richer ``seller`` / ``buyer`` /
    ``lines`` structures to build the UBL 2.1 document; these carry defaults so
    the mock and unit tests can build a payload without the full graph.
    """

    document_no: str
    invoice_type: str          # "INVOICE" | "SELF_BILLED" | "CONSOLIDATED" | "CREDIT_NOTE"
    business_date: str         # ISO date
    currency: str              # ISO 4217
    exchange_rate: Decimal
    seller_tin: str
    seller_name: str
    seller_msic_code: Optional[str]
    seller_sst_no: Optional[str]
    buyer_tin: str
    buyer_name: str
    buyer_msic_code: Optional[str]
    subtotal_excl_tax: Decimal
    tax_amount: Decimal
    total_incl_tax: Decimal
    line_count: int

    # ── Rich structures (real adapter only) ──────────────────────────────────
    seller: Optional[PartyInfo] = None
    buyer: Optional[PartyInfo] = None
    lines: tuple[LinePayload, ...] = field(default_factory=tuple)
    issue_time: Optional[str] = None            # "HH:MM:SSZ"; defaults to now
    discount_amount: Decimal = Decimal("0")
    # Credit Note only — UBL BillingReference back to the original invoice.
    original_uin: Optional[str] = None
    original_document_no: Optional[str] = None


@dataclass(frozen=True)
class SubmitResult:
    """Outcome of a submission.

    ``validated_at`` is ``None`` when LHDN accepted the document but has not
    finished validating it within the adapter's poll budget. Callers must then
    park the invoice in ``SUBMITTED`` and reconcile later via ``get_status`` —
    the document is already lodged with LHDN, so re-submitting would trip the
    10-minute duplicate check.
    """

    uin: str
    qr_code_url: Optional[str]
    submitted_at: datetime
    validated_at: Optional[datetime]
    submission_uid: Optional[str] = None


@dataclass(frozen=True)
class StatusResult:
    uin: str
    status: str                # "SUBMITTED" | "VALIDATED" | "REJECTED" | "FINAL"
    validated_at: Optional[datetime]
    rejection_reason: Optional[str]
    qr_code_url: Optional[str] = None


@dataclass(frozen=True)
class RejectResult:
    uin: str
    rejected_at: datetime
    success: bool


# ── Protocol ─────────────────────────────────────────────────────────────────


class MyInvoisAdapter(Protocol):
    """Contract for any MyInvois integration (mock / sandbox / production)."""

    async def submit(self, payload: InvoicePayload) -> SubmitResult:
        """Submit an invoice and return UIN + QR + timestamps.

        Mock returns synchronously with a fake UIN and a populated
        ``validated_at``. The real adapter performs the OAuth handshake, posts
        the UBL document and polls for the outcome; ``validated_at`` may come
        back ``None`` (see :class:`SubmitResult`).
        """
        ...

    async def get_status(self, uin: str) -> StatusResult:
        """Fetch current status of a submitted invoice from LHDN."""
        ...

    async def reject(self, uin: str, *, reason: str) -> RejectResult:
        """Mark an invoice as rejected (within the 72h opposition window)."""
        ...
