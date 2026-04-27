"""
DocumentSequenceService — atomic document number generation.

Uses Redis INCR for atomicity, writes back to document_sequences table for audit/recovery.

Format: {PREFIX}-{YEAR}-{5-digit zero-padded}
Example: PO-2026-00042
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import redis_default
from app.models.audit import DocumentSequence

logger = structlog.get_logger()

# Prefix mapping
DOC_PREFIXES: dict[str, str] = {
    "PO": "PO",
    "SO": "SO",
    "INV": "INV",
    "CN": "CN",
    "GR": "GR",
    "DO": "DO",
    "TR": "TR",
    "ADJ": "ADJ",
    "QT": "QT",
}


async def next_document_no(
    session: AsyncSession,
    doc_type: str,
    org_id: int,
    *,
    year: int | None = None,
) -> str:
    """
    Generate the next document number atomically.

    Args:
        session:  Active AsyncSession (used for DB write-back).
        doc_type: One of DOC_PREFIXES keys, e.g. "PO".
        org_id:   Organization ID for namespace isolation.
        year:     Override the year (defaults to current UTC year).

    Returns:
        Formatted document number string, e.g. "PO-2026-00042".
    """
    if doc_type not in DOC_PREFIXES:
        raise ValueError(f"Unknown doc_type: {doc_type!r}")

    if year is None:
        year = datetime.now(UTC).year

    redis_key = f"seq:{org_id}:{doc_type}:{year}"
    value: int = await redis_default.incr(redis_key)

    # Write back to DB (best-effort — not in the same transaction to avoid coupling)
    await _upsert_sequence_record(session, org_id, doc_type, year, value)

    prefix = DOC_PREFIXES[doc_type]
    doc_no = f"{prefix}-{year}-{value:05d}"

    logger.debug("document_no_generated", doc_type=doc_type, org_id=org_id, doc_no=doc_no)
    return doc_no


async def _upsert_sequence_record(
    session: AsyncSession,
    org_id: int,
    doc_type: str,
    year: int,
    current_value: int,
) -> None:
    """Upsert document_sequences row to keep DB in sync with Redis."""
    now = datetime.now(UTC).replace(tzinfo=None)
    stmt = select(DocumentSequence).where(
        DocumentSequence.organization_id == org_id,
        DocumentSequence.doc_type == doc_type,
        DocumentSequence.year == year,
    )
    result = await session.execute(stmt)
    rec = result.scalar_one_or_none()

    if rec is None:
        rec = DocumentSequence(
            organization_id=org_id,
            doc_type=doc_type,
            year=year,
            current_value=current_value,
            last_generated_at=now,
        )
        session.add(rec)
    else:
        rec.current_value = current_value
        rec.last_generated_at = now
        session.add(rec)
