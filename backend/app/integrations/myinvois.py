"""MyInvois adapter Protocol — stable contract for LHDN e-Invoice integration.

The Mock implementation lives in ``myinvois_mock.py`` and is selected by the
factory in mock mode. A future ``myinvois_real.py`` (sandbox or production)
will implement the same Protocol with OAuth 2.0, UBL 2.1 XML payloads and
digital-certificate signing — service-layer code stays untouched.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional, Protocol


# ── DTOs ─────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class InvoicePayload:
    """Provider-agnostic invoice payload submitted to MyInvois.

    Mirrors LHDN UBL 2.1 essential fields. Real adapter serialises this to
    XML; mock adapter just inspects it for shape verification.
    """

    document_no: str
    invoice_type: str          # "INVOICE" | "SELF_BILLED" | "CONSOLIDATED"
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


@dataclass(frozen=True)
class SubmitResult:
    uin: str
    qr_code_url: str
    submitted_at: datetime
    validated_at: datetime


@dataclass(frozen=True)
class StatusResult:
    uin: str
    status: str                # "SUBMITTED" | "VALIDATED" | "REJECTED" | "FINAL"
    validated_at: Optional[datetime]
    rejection_reason: Optional[str]


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

        Mock returns synchronously with a fake UIN. Real LHDN adapter performs
        OAuth handshake, signs UBL XML, posts and polls until VALIDATED.
        """
        ...

    async def get_status(self, uin: str) -> StatusResult:
        """Fetch current status of a submitted invoice from LHDN."""
        ...

    async def reject(self, uin: str, *, reason: str) -> RejectResult:
        """Mark an invoice as rejected (within the 72h opposition window)."""
        ...
