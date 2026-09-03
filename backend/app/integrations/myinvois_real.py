"""Real MyInvois adapter — talks to LHDN over HTTP.

Submission is a two-phase affair on LHDN's side:

1. ``POST /api/v1.0/documentsubmissions`` returns 202 with a ``submissionUid``
   and, per document, either an accepted ``uuid`` or a rejection.
2. Validation then runs asynchronously. ``GET /api/v1.0/documents/{uuid}/details``
   reports ``Submitted`` until it settles on ``Valid`` / ``Invalid``.

This adapter polls step 2 a bounded number of times. If validation has not
settled within that budget it returns ``validated_at=None`` — the caller parks
the invoice in ``SUBMITTED`` and reconciles later. It must never re-submit: the
document is already lodged, and LHDN rejects identical submissions made within
10 minutes.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Optional

import structlog

from app.core.exceptions import MyInvoisError, MyInvoisRejectedError
from app.integrations.myinvois import (
    InvoicePayload,
    MyInvoisAdapter,
    RejectResult,
    StatusResult,
    SubmitResult,
)
from app.integrations.myinvois_http import (
    DOCUMENT_DETAILS_PATH,
    DOCUMENT_STATE_PATH,
    SUBMIT_PATH,
    MyInvoisHttpClient,
)
from app.integrations.myinvois_ubl import build_invoice_document

logger = structlog.get_logger()

# LHDN document status → our InvoiceStatus vocabulary.
_STATUS_MAP: dict[str, str] = {
    "submitted": "SUBMITTED",
    "valid": "VALIDATED",
    "invalid": "REJECTED",
    "cancelled": "REJECTED",
}

# LHDN caps a single e-Invoice at 300 KB.
_MAX_DOCUMENT_BYTES = 300 * 1024


def _now() -> datetime:
    """Naive UTC — matches how the ORM stores timestamps (rule A5)."""
    return datetime.now(UTC).replace(tzinfo=None)


def _parse_lhdn_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse an LHDN ISO-8601 UTC timestamp into a naive UTC datetime."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        logger.warning("myinvois_unparseable_datetime", value=value)
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed


def encode_document(document: dict[str, Any]) -> tuple[str, str]:
    """Minify, hash and base64-encode a UBL document.

    Returns ``(base64_document, sha256_hex)``. The hash is taken over the exact
    minified UTF-8 bytes that are encoded, so the two always agree.
    """
    minified = json.dumps(document, separators=(",", ":"), ensure_ascii=False)
    raw = minified.encode("utf-8")
    if len(raw) > _MAX_DOCUMENT_BYTES:
        raise MyInvoisError(
            message="Document exceeds the LHDN 300 KB per-invoice limit.",
            error_code="MYINVOIS_DOCUMENT_TOO_LARGE",
            detail={"size_bytes": len(raw), "limit_bytes": _MAX_DOCUMENT_BYTES},
        )
    return base64.b64encode(raw).decode("ascii"), hashlib.sha256(raw).hexdigest()


def _validation_summary(details: dict[str, Any]) -> Optional[str]:
    """Flatten LHDN's nested validationResults into a one-line reason."""
    results = details.get("validationResults") or {}
    steps = results.get("validationSteps") or []
    failures = [
        step.get("name") or "validation"
        for step in steps
        if isinstance(step, dict) and str(step.get("status", "")).lower() == "invalid"
    ]
    if failures:
        return "LHDN validation failed: " + ", ".join(failures)
    status = results.get("status")
    return f"LHDN validation status: {status}" if status else None


class MyInvoisRealAdapter(MyInvoisAdapter):
    """MyInvois adapter backed by the LHDN REST API (preprod or production)."""

    def __init__(
        self,
        client: MyInvoisHttpClient,
        *,
        poll_attempts: int = 3,
        poll_interval_seconds: float = 2.0,
    ) -> None:
        self._client = client
        self._poll_attempts = max(poll_attempts, 1)
        self._poll_interval = poll_interval_seconds

    # ── Submit ───────────────────────────────────────────────────────────────

    async def submit(self, payload: InvoicePayload) -> SubmitResult:
        document = build_invoice_document(payload)
        encoded, document_hash = encode_document(document)

        body = {
            "documents": [
                {
                    "format": "JSON",
                    "document": encoded,
                    "documentHash": document_hash,
                    "codeNumber": payload.document_no,
                }
            ]
        }
        submitted_at = _now()
        response = await self._client.post_json(SUBMIT_PATH, body)

        rejected = response.get("rejectedDocuments") or []
        if rejected:
            logger.warning(
                "myinvois_submission_rejected",
                document_no=payload.document_no,
                rejected=rejected,
            )
            raise MyInvoisRejectedError(
                message="LHDN MyInvois rejected this document at submission.",
                detail={"rejectedDocuments": rejected},
            )

        accepted = response.get("acceptedDocuments") or []
        if not accepted:
            raise MyInvoisError(
                message="MyInvois accepted neither nor rejected the document.",
                error_code="MYINVOIS_EMPTY_SUBMISSION_RESULT",
                detail={"response": response},
            )

        uuid = accepted[0].get("uuid")
        if not uuid:
            raise MyInvoisError(
                message="MyInvois response did not include a document uuid.",
                error_code="MYINVOIS_BAD_RESPONSE",
                detail={"response": response},
            )
        # LHDN spells this "submissionUID" in the API reference and
        # "submissionUid" in the details payload; accept either.
        submission_uid = response.get("submissionUid") or response.get("submissionUID")

        logger.info(
            "myinvois_submitted",
            document_no=payload.document_no,
            uuid=uuid,
            submission_uid=submission_uid,
        )

        details = await self._poll_until_settled(uuid)
        status = str(details.get("status", "")).lower()
        if status == "invalid":
            raise MyInvoisRejectedError(
                message=_validation_summary(details)
                or "LHDN MyInvois marked this document invalid.",
                detail={"uuid": uuid, "validationResults": details.get("validationResults")},
            )

        validated_at = (
            _parse_lhdn_datetime(details.get("dateTimeValidated")) if status == "valid" else None
        )
        if status == "valid" and validated_at is None:
            # Validated but LHDN omitted the timestamp — trust the status.
            validated_at = _now()

        return SubmitResult(
            uin=uuid,
            qr_code_url=self._share_url(uuid, details.get("longId")),
            submitted_at=submitted_at,
            validated_at=validated_at,
            submission_uid=submission_uid,
        )

    async def _poll_until_settled(self, uuid: str) -> dict[str, Any]:
        """Poll document details until it leaves ``Submitted``, or budget runs out."""
        details: dict[str, Any] = {}
        for attempt in range(self._poll_attempts):
            details = await self._client.get_json(DOCUMENT_DETAILS_PATH.format(uuid=uuid))
            status = str(details.get("status", "")).lower()
            if status and status != "submitted":
                return details
            if attempt < self._poll_attempts - 1:
                await asyncio.sleep(self._poll_interval)
        logger.info("myinvois_validation_pending", uuid=uuid, attempts=self._poll_attempts)
        return details

    def _share_url(self, uuid: str, long_id: Optional[str]) -> Optional[str]:
        """Public validation link — only exists once LHDN issues a longId."""
        if not long_id:
            return None
        return f"{self._client.portal_base_url}/{uuid}/share/{long_id}"

    # ── Status ───────────────────────────────────────────────────────────────

    async def get_status(self, uin: str) -> StatusResult:
        details = await self._client.get_json(DOCUMENT_DETAILS_PATH.format(uuid=uin))
        raw_status = str(details.get("status", "")).lower()
        status = _STATUS_MAP.get(raw_status)
        if status is None:
            raise MyInvoisError(
                message=f"MyInvois returned an unknown document status {raw_status!r}.",
                error_code="MYINVOIS_UNKNOWN_STATUS",
                detail={"uuid": uin, "status": details.get("status")},
            )
        return StatusResult(
            uin=uin,
            status=status,
            validated_at=_parse_lhdn_datetime(details.get("dateTimeValidated")),
            rejection_reason=(
                _validation_summary(details) if status == "REJECTED" else None
            ),
            qr_code_url=self._share_url(uin, details.get("longId")),
        )

    # ── Reject ───────────────────────────────────────────────────────────────

    async def reject(self, uin: str, *, reason: str) -> RejectResult:
        await self._client.put_json(
            DOCUMENT_STATE_PATH.format(uuid=uin),
            {"status": "Rejected", "reason": reason},
        )
        logger.info("myinvois_rejection_requested", uuid=uin)
        return RejectResult(uin=uin, rejected_at=_now(), success=True)
