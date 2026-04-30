"""
DocumentSequenceService — atomic document number generation.

Uses Redis INCR for atomicity, writes back to document_sequences table for audit/recovery.

Format: {PREFIX}-{YEAR}-{5-digit zero-padded}
Example: PO-2026-00042
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlalchemy import select, text
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

# doc_type -> business table (self-heal reads MAX(document_no) here so the
# sequence catches up to rows inserted out-of-band — seed scripts, manual
# patches, restored snapshots).
DOC_TYPE_TABLES: dict[str, str] = {
    "PO": "purchase_orders",
    "SO": "sales_orders",
    "DO": "delivery_orders",
    "GR": "goods_receipts",
    "INV": "invoices",
    "CN": "credit_notes",
    "TR": "stock_transfers",
    "ADJ": "stock_adjustments",
    "QT": "quotations",
}

# Atomic max-update + INCR. SETNX + INCR cannot recover when Redis already
# holds a stale value lower than the true max — Lua serializes the read,
# conditional bump, and increment so concurrent callers cannot interleave.
_INCR_WITH_FLOOR_LUA = """
local cur = tonumber(redis.call('GET', KEYS[1]) or '0')
local seed = tonumber(ARGV[1])
if cur < seed then
    redis.call('SET', KEYS[1], seed)
end
return redis.call('INCR', KEYS[1])
"""


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

    # Self-heal seed = max(persisted sequence, real business-table max).
    # The business table is the only authoritative source for "already used"
    # numbers — document_sequences and Redis are derived caches that may lag
    # behind seeded / restored / manually-patched data. Picking the true max
    # guarantees the next INCR yields an unused number on the very first try.
    db_seed = max(
        await _read_db_current_value(session, org_id, doc_type, year),
        await _read_table_max_value(session, org_id, doc_type, year),
    )
    value = int(
        await redis_default.eval(_INCR_WITH_FLOOR_LUA, 1, redis_key, db_seed)
    )

    # Write back to DB (best-effort — not in the same transaction to avoid coupling)
    await _upsert_sequence_record(session, org_id, doc_type, year, value)

    prefix = DOC_PREFIXES[doc_type]
    doc_no = f"{prefix}-{year}-{value:05d}"

    logger.debug("document_no_generated", doc_type=doc_type, org_id=org_id, doc_no=doc_no)
    return doc_no


async def _read_db_current_value(
    session: AsyncSession,
    org_id: int,
    doc_type: str,
    year: int,
) -> int:
    """Return the last persisted sequence value for (org, doc_type, year), or 0."""
    stmt = select(DocumentSequence.current_value).where(
        DocumentSequence.organization_id == org_id,
        DocumentSequence.doc_type == doc_type,
        DocumentSequence.year == year,
    )
    val = (await session.execute(stmt)).scalar_one_or_none()
    return val or 0


async def _read_table_max_value(
    session: AsyncSession,
    org_id: int,
    doc_type: str,
    year: int,
) -> int:
    """Return the highest sequence number already written to the business table.

    5-digit zero padding makes lexicographic MAX equal to numeric MAX, so a plain
    MAX(document_no) is sufficient — no CAST/SUBSTR needed.
    """
    table = DOC_TYPE_TABLES.get(doc_type)
    if not table:
        return 0
    prefix = DOC_PREFIXES[doc_type]
    pattern = f"{prefix}-{year}-%"
    sql = text(
        f"SELECT MAX(document_no) FROM {table} "
        f"WHERE organization_id = :org AND document_no LIKE :pat"
    )
    max_doc_no = (
        await session.execute(sql, {"org": org_id, "pat": pattern})
    ).scalar_one_or_none()
    if not max_doc_no:
        return 0
    try:
        return int(max_doc_no.rsplit("-", 1)[-1])
    except (ValueError, IndexError):
        logger.warning("malformed_document_no", value=max_doc_no, table=table)
        return 0


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
        # Monotonic: never let the persisted value go backwards. Protects the
        # self-heal seed against a transient Redis reset that briefly produces
        # smaller values while filling historical holes.
        if current_value > rec.current_value:
            rec.current_value = current_value
        rec.last_generated_at = now
        session.add(rec)
