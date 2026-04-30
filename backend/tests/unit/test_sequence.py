"""Unit tests for `next_document_no` self-heal logic.

Covers the bug fixed at sequence.py: when the business table held rows whose
document_no exceeded `document_sequences.current_value` (typical after seed
scripts / restored snapshots / Redis container rebuilds), Redis INCR returned
an already-used number, producing a unique-key collision. The fix seeds Redis
from `max(document_sequences.current_value, MAX(business_table.document_no))`
inside an atomic Lua script.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import sequence as sequence_module
from app.services.sequence import next_document_no


@pytest.mark.asyncio
@patch("app.services.sequence._upsert_sequence_record", new_callable=AsyncMock)
@patch("app.services.sequence._read_table_max_value", new_callable=AsyncMock)
@patch("app.services.sequence._read_db_current_value", new_callable=AsyncMock)
@patch.object(sequence_module, "redis_default")
async def test_first_ever_call_returns_00001(
    mock_redis: MagicMock,
    mock_db_current: AsyncMock,
    mock_table_max: AsyncMock,
    _mock_upsert: AsyncMock,
) -> None:
    """Empty Redis + empty document_sequences + empty business table → 00001."""
    mock_db_current.return_value = 0
    mock_table_max.return_value = 0
    mock_redis.eval = AsyncMock(return_value=1)

    result = await next_document_no(AsyncMock(), "SO", org_id=1, year=2026)

    assert result == "SO-2026-00001"
    seed_passed = mock_redis.eval.call_args.args[3]
    assert seed_passed == 0


@pytest.mark.asyncio
@patch("app.services.sequence._upsert_sequence_record", new_callable=AsyncMock)
@patch("app.services.sequence._read_table_max_value", new_callable=AsyncMock)
@patch("app.services.sequence._read_db_current_value", new_callable=AsyncMock)
@patch.object(sequence_module, "redis_default")
async def test_business_table_ahead_of_sequence_record_uses_table_max(
    mock_redis: MagicMock,
    mock_db_current: AsyncMock,
    mock_table_max: AsyncMock,
    _mock_upsert: AsyncMock,
) -> None:
    """Regression: seed scripts wrote SO-2026-00009 directly; document_sequences
    only knows current_value=3. Seed MUST be 9 so the next number is 10, not 4."""
    mock_db_current.return_value = 3
    mock_table_max.return_value = 9
    mock_redis.eval = AsyncMock(return_value=10)

    result = await next_document_no(AsyncMock(), "SO", org_id=1, year=2026)

    assert result == "SO-2026-00010"
    seed_passed = mock_redis.eval.call_args.args[3]
    assert seed_passed == 9


@pytest.mark.asyncio
@patch("app.services.sequence._upsert_sequence_record", new_callable=AsyncMock)
@patch("app.services.sequence._read_table_max_value", new_callable=AsyncMock)
@patch("app.services.sequence._read_db_current_value", new_callable=AsyncMock)
@patch.object(sequence_module, "redis_default")
async def test_sequence_record_ahead_of_business_table_uses_db_value(
    mock_redis: MagicMock,
    mock_db_current: AsyncMock,
    mock_table_max: AsyncMock,
    _mock_upsert: AsyncMock,
) -> None:
    """Mirror case: business rows were soft-deleted but document_sequences kept
    the higher counter. Seed must be the larger of the two."""
    mock_db_current.return_value = 50
    mock_table_max.return_value = 12
    mock_redis.eval = AsyncMock(return_value=51)

    result = await next_document_no(AsyncMock(), "PO", org_id=1, year=2026)

    assert result == "PO-2026-00051"
    seed_passed = mock_redis.eval.call_args.args[3]
    assert seed_passed == 50


@pytest.mark.asyncio
async def test_unknown_doc_type_raises() -> None:
    with pytest.raises(ValueError, match="Unknown doc_type"):
        await next_document_no(AsyncMock(), "ZZZ", org_id=1, year=2026)


@pytest.mark.asyncio
async def test_read_table_max_value_parses_zero_padded_suffix() -> None:
    """Verify _read_table_max_value extracts the integer suffix from MAX()."""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value="SO-2026-00042")
    session.execute = AsyncMock(return_value=result)

    value = await sequence_module._read_table_max_value(
        session, org_id=1, doc_type="SO", year=2026
    )

    assert value == 42


@pytest.mark.asyncio
async def test_read_table_max_value_returns_zero_for_unknown_doc_type() -> None:
    session = AsyncMock()
    value = await sequence_module._read_table_max_value(
        session, org_id=1, doc_type="UNKNOWN", year=2026
    )
    assert value == 0
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_read_table_max_value_returns_zero_when_table_empty() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=result)

    value = await sequence_module._read_table_max_value(
        session, org_id=1, doc_type="SO", year=2026
    )

    assert value == 0


@pytest.mark.asyncio
async def test_read_table_max_value_handles_malformed_doc_no() -> None:
    """A malformed document_no (missing/non-numeric suffix) must not crash."""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value="SO-2026-XYZ")
    session.execute = AsyncMock(return_value=result)

    value = await sequence_module._read_table_max_value(
        session, org_id=1, doc_type="SO", year=2026
    )

    assert value == 0


def test_doc_type_tables_covers_all_prefixes() -> None:
    """Every prefix the service can format must have a business table mapping,
    otherwise the self-heal silently degrades to legacy behavior."""
    assert set(sequence_module.DOC_PREFIXES) <= set(sequence_module.DOC_TYPE_TABLES)
