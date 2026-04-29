"""Unit tests for the Consolidated Invoice flow (Window 12).

Mocks the SQL queries (since SQLAlchemy expressions are awkward to assert on)
and verifies the dispatching, grouping and exclusion logic. Per-line totals
are smoke-tested via the happy path; full math coverage lives in
test_einvoice_service.py for ``generate_draft_from_so``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import BusinessRuleError
from app.enums import (
    InvoiceStatus,
    InvoiceType,
    RoleCode,
    SOStatus,
)
from app.schemas.invoice import GenerateFromSOIn
from app.services import einvoice as svc
from tests.conftest import make_mock_session, make_mock_user


def _make_so_line(
    sol_id: int = 100,
    qty_shipped: Decimal = Decimal("3"),
) -> MagicMock:
    sol = MagicMock()
    sol.id = sol_id
    sol.line_no = 1
    sol.sku_id = 11
    sol.uom_id = 1
    sol.description = "Item"
    sol.qty_shipped = qty_shipped
    sol.qty_invoiced = Decimal("0")
    sol.unit_price_excl_tax = Decimal("100.00")
    sol.tax_rate_id = 1
    sol.tax_rate_percent = Decimal("10.00")
    sol.discount_amount = Decimal("0")
    sku = MagicMock()
    sku.name = "Test SKU"
    sku.msic_code = "47190"
    sol.sku = sku
    return sol


def _make_so(
    *,
    so_id: int = 1,
    customer_id: int = 7,
    status: SOStatus = SOStatus.FULLY_SHIPPED,
    business_date: date = date(2026, 3, 15),
    line_count: int = 1,
) -> MagicMock:
    so = MagicMock()
    so.id = so_id
    so.organization_id = 1
    so.document_no = f"SO-2026-{so_id:05d}"
    so.status = status
    so.customer_id = customer_id
    so.warehouse_id = 1
    so.business_date = business_date
    so.currency = "MYR"
    so.exchange_rate = Decimal("1")
    so.payment_terms_days = 30
    so.lines = [_make_so_line(sol_id=100 + i) for i in range(line_count)]
    return so


# ── _month_bounds ────────────────────────────────────────────────────────────


def test_month_bounds_handles_28_29_30_31():
    assert svc._month_bounds(2026, 1) == (date(2026, 1, 1), date(2026, 1, 31))
    assert svc._month_bounds(2024, 2) == (date(2024, 2, 1), date(2024, 2, 29))  # leap
    assert svc._month_bounds(2026, 4) == (date(2026, 4, 1), date(2026, 4, 30))


# ── generate_monthly_consolidated ────────────────────────────────────────────


def _patch_consolidation_queries(
    *,
    individually_invoiced: list[int],
    already_consolidated: set[int],
    candidate_sos: list[MagicMock],
):
    """Wire up the three queries inside generate_monthly_consolidated.

    The function calls session.execute three times in sequence:
      1. SO ids already individually invoiced
      2. SO ids already in a CONSOLIDATED (via _consolidated_so_ids)
      3. Candidate B2C SOs in the month
    Plus a session.get(Organization, ...) call for MSIC fallback.
    """
    individual_result = MagicMock()
    individual_result.all = MagicMock(return_value=[(soid,) for soid in individually_invoiced])

    consolidated_result = MagicMock()
    consolidated_result.all = MagicMock(return_value=[(soid,) for soid in already_consolidated])

    candidate_result = MagicMock()
    scalars_obj = MagicMock()
    scalars_obj.all = MagicMock(return_value=candidate_sos)
    candidate_result.scalars = MagicMock(return_value=scalars_obj)

    return [individual_result, consolidated_result, candidate_result]


def _make_session_with_executes(execute_results: list, org_msic: str | None = "47190"):
    session = make_mock_session()
    session.execute = AsyncMock(side_effect=execute_results)
    org_row = MagicMock()
    org_row.msic_code = org_msic
    session.get = AsyncMock(return_value=org_row)

    # Auto-assign incrementing ids to any Invoice the service adds, since the
    # production code reads ``invoice.id`` after flush. Real DB does this; our
    # AsyncMock flush does not.
    counter = {"next_id": 1000}
    invoices: list = []

    def _add(obj):
        if obj.__class__.__name__ == "Invoice" and getattr(obj, "id", None) is None:
            obj.id = counter["next_id"]
            counter["next_id"] += 1
            invoices.append(obj)

    session.add.side_effect = _add
    session._captured_invoices = invoices  # for tests to inspect
    return session


@pytest.mark.asyncio
async def test_consolidated_groups_by_customer():
    """Two B2C customers, three SOs total → two invoices generated."""
    user = make_mock_user(role=RoleCode.ADMIN)
    so1 = _make_so(so_id=1, customer_id=7)
    so2 = _make_so(so_id=2, customer_id=7)  # same customer as so1
    so3 = _make_so(so_id=3, customer_id=8)

    session = _make_session_with_executes(
        _patch_consolidation_queries(
            individually_invoiced=[],
            already_consolidated=set(),
            candidate_sos=[so1, so2, so3],
        )
    )

    # SalesOrderRepository.get_detail returns the same so by id
    by_id = {1: so1, 2: so2, 3: so3}
    so_repo = MagicMock()
    so_repo.get_detail = AsyncMock(side_effect=lambda org_id, sid: by_id.get(sid))

    seq_counter = iter(["INV-2026-CONS01", "INV-2026-CONS02"])

    with (
        patch.object(svc, "SalesOrderRepository", return_value=so_repo),
        patch.object(svc, "next_document_no", new=AsyncMock(side_effect=lambda *a, **kw: next(seq_counter))),
    ):
        result = await svc.generate_monthly_consolidated(
            session, org_id=1, user=user, year=2026, month=3,
        )

    assert result.generated_count == 2
    assert sorted(result.customer_ids) == [7, 8]
    assert result.year == 2026
    assert result.month == 3


@pytest.mark.asyncio
async def test_consolidated_returns_empty_when_no_candidates():
    user = make_mock_user(role=RoleCode.ADMIN)

    session = _make_session_with_executes(
        _patch_consolidation_queries(
            individually_invoiced=[],
            already_consolidated=set(),
            candidate_sos=[],
        )
    )

    with patch.object(svc, "SalesOrderRepository") as repo_cls:
        result = await svc.generate_monthly_consolidated(
            session, org_id=1, user=user, year=2026, month=3,
        )

    assert result.generated_count == 0
    assert result.customer_ids == []
    assert result.invoice_ids == []
    repo_cls.assert_not_called()  # no SO loading attempted


@pytest.mark.asyncio
async def test_consolidated_skips_so_with_no_shipped_lines():
    """A B2C SO that's somehow PARTIAL_SHIPPED with all qty_shipped=0 is skipped."""
    user = make_mock_user(role=RoleCode.ADMIN)
    so_empty = _make_so(so_id=10, customer_id=7)
    so_empty.lines = [_make_so_line(qty_shipped=Decimal("0"))]

    session = _make_session_with_executes(
        _patch_consolidation_queries(
            individually_invoiced=[],
            already_consolidated=set(),
            candidate_sos=[so_empty],
        )
    )
    so_repo = MagicMock()
    so_repo.get_detail = AsyncMock(return_value=so_empty)

    with (
        patch.object(svc, "SalesOrderRepository", return_value=so_repo),
        patch.object(svc, "next_document_no", new=AsyncMock(return_value="INV-2026-X")),
    ):
        result = await svc.generate_monthly_consolidated(
            session, org_id=1, user=user, year=2026, month=3,
        )

    assert result.generated_count == 0


@pytest.mark.asyncio
async def test_consolidated_invoice_has_correct_type_and_no_so_link():
    """Verify the generated Invoice is tagged CONSOLIDATED with sales_order_id=NULL."""
    user = make_mock_user(role=RoleCode.ADMIN)
    so = _make_so(so_id=1, customer_id=7, line_count=2)

    session = _make_session_with_executes(
        _patch_consolidation_queries(
            individually_invoiced=[],
            already_consolidated=set(),
            candidate_sos=[so],
        )
    )
    so_repo = MagicMock()
    so_repo.get_detail = AsyncMock(return_value=so)

    with (
        patch.object(svc, "SalesOrderRepository", return_value=so_repo),
        patch.object(svc, "next_document_no", new=AsyncMock(return_value="INV-2026-CONS")),
    ):
        await svc.generate_monthly_consolidated(
            session, org_id=1, user=user, year=2026, month=3,
        )

    # Exactly one Invoice was created (1 customer).
    assert len(session._captured_invoices) == 1
    inv = session._captured_invoices[0]
    assert inv.invoice_type == InvoiceType.CONSOLIDATED
    assert inv.sales_order_id is None  # consolidated has no single SO
    assert inv.status == InvoiceStatus.DRAFT
    assert inv.customer_id == 7


# ── _so_already_consolidated guard in generate_draft_from_so ─────────────────


@pytest.mark.asyncio
async def test_generate_draft_blocks_so_already_in_consolidated():
    session = make_mock_session()
    so = _make_so(status=SOStatus.FULLY_SHIPPED)
    user = make_mock_user(role=RoleCode.SALES)

    so_repo = MagicMock()
    so_repo.get_detail = AsyncMock(return_value=so)
    inv_repo = MagicMock()
    inv_repo.get_by_so_id = AsyncMock(return_value=None)

    with (
        patch.object(svc, "SalesOrderRepository", return_value=so_repo),
        patch.object(svc, "InvoiceRepository", return_value=inv_repo),
        patch.object(svc, "_so_already_consolidated", new=AsyncMock(return_value=True)),
    ):
        with pytest.raises(BusinessRuleError) as exc:
            await svc.generate_draft_from_so(
                session, so_id=1, org_id=1, user=user, payload=GenerateFromSOIn(),
            )
    assert exc.value.error_code == "SO_ALREADY_CONSOLIDATED"
