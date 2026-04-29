"""Mock MyInvois adapter.

Synchronous deterministic mock used for local dev, demo and tests. Generates
a fake UIN and QR code URL, returns immediately. State machine downstream
treats the response as if LHDN accepted and validated the invoice in one
round-trip.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import structlog

from app.integrations.myinvois import (
    InvoicePayload,
    MyInvoisAdapter,
    RejectResult,
    StatusResult,
    SubmitResult,
)

logger = structlog.get_logger()


_MOCK_QR_BASE = "https://myinvois-mock.local/qr"


def _make_uin() -> str:
    """Generate a 16-char hex UIN, deterministic enough for logs but unique."""
    return uuid4().hex[:16].upper()


class MyInvoisMockAdapter(MyInvoisAdapter):
    """In-process mock — no network, no auth, no XML."""

    async def submit(self, payload: InvoicePayload) -> SubmitResult:
        now = datetime.now(UTC).replace(tzinfo=None)
        uin = _make_uin()
        qr_url = f"{_MOCK_QR_BASE}/{uin}"
        logger.info(
            "myinvois_mock_submit",
            document_no=payload.document_no,
            seller_tin=payload.seller_tin,
            buyer_tin=payload.buyer_tin,
            total=str(payload.total_incl_tax),
            uin=uin,
        )
        return SubmitResult(
            uin=uin,
            qr_code_url=qr_url,
            submitted_at=now,
            validated_at=now,
        )

    async def get_status(self, uin: str) -> StatusResult:
        # Mock has no persistent state — the caller is expected to read the
        # invoice row itself. This is here for Protocol completeness.
        logger.debug("myinvois_mock_get_status", uin=uin)
        return StatusResult(
            uin=uin,
            status="VALIDATED",
            validated_at=datetime.now(UTC).replace(tzinfo=None),
            rejection_reason=None,
        )

    async def reject(self, uin: str, *, reason: str) -> RejectResult:
        logger.info("myinvois_mock_reject", uin=uin, reason=reason)
        return RejectResult(
            uin=uin,
            rejected_at=datetime.now(UTC).replace(tzinfo=None),
            success=True,
        )
