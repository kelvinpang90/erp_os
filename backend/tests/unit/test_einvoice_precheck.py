"""Unit tests for the e-Invoice precheck service (Window 12).

Covers:
  1. Hard rule happy path — all 7 hard items pass on a well-formed invoice.
  2. Hard rule failure — SST sum mismatch flips SST_TAX_AMOUNT_CONSISTENT to FAIL.
  3. Hard rule failure — B2B buyer with empty TIN flips BUYER_TIN_PRESENT_OR_B2C.
  4. Overall status downgrades to WARN when only WARN-severity items fail
     (a soft rule from the LLM).
  5. AI gate disabled → soft rules degrade to passing placeholders, ai_used=False,
     AICallLog row written with status=DISABLED.
  6. LLM timeout → degraded soft items, ai_error=LLM_TIMEOUT, log row TIMEOUT.
  7. LLM happy path → 3 soft items returned, ai_used=True.
  8. Invoice not found → NotFoundError.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import NotFoundError
from app.enums import (
    AICallStatus,
    CustomerType,
    InvoiceStatus,
    InvoiceType,
    RoleCode,
)
from app.services import einvoice_precheck as svc
from tests.conftest import make_mock_session, make_mock_user


# ── Fixture builders ─────────────────────────────────────────────────────────


def _make_inv(
    *,
    seller_tin: str = "C1234567890",
    seller_msic: str | None = "47190",
    buyer_tin: str = "C9999999999",
    buyer_type: CustomerType = CustomerType.B2B,
    buyer_name: str = "Buyer Sdn Bhd",
    line_tax_rates: tuple[Decimal, ...] = (Decimal("10.00"),),
    sst_inconsistent: bool = False,
    subtotal_inconsistent: bool = False,
    currency: str = "MYR",
    exchange_rate: Decimal = Decimal("1"),
    line_msic: str | None = "47190",
) -> MagicMock:
    inv = MagicMock()
    inv.id = 5
    inv.organization_id = 1
    inv.document_no = "INV-2026-00001"
    inv.invoice_type = InvoiceType.INVOICE
    inv.status = InvoiceStatus.DRAFT
    inv.currency = currency
    inv.exchange_rate = exchange_rate
    inv.business_date = date(2026, 4, 15)

    org = MagicMock()
    org.tin = seller_tin
    org.name = "Demo Sdn Bhd"
    org.msic_code = seller_msic
    inv.organization = org

    cust = MagicMock()
    cust.id = 7
    cust.name = buyer_name
    cust.tin = buyer_tin
    cust.customer_type = buyer_type
    cust.msic_code = None
    inv.customer = cust

    lines: list[MagicMock] = []
    line_excl_each = Decimal("100.00")
    for i, rate in enumerate(line_tax_rates, start=1):
        ln = MagicMock()
        ln.line_no = i
        ln.description = f"Test product {i} (5kg pack)"
        ln.qty = Decimal("1")
        ln.unit_price_excl_tax = line_excl_each
        ln.tax_rate_percent = rate
        ln.tax_amount = (line_excl_each * rate / Decimal("100")).quantize(Decimal("0.01"))
        ln.line_total_excl_tax = line_excl_each
        ln.line_total_incl_tax = line_excl_each + ln.tax_amount
        ln.msic_code = line_msic
        lines.append(ln)
    inv.lines = lines

    sum_excl = sum((ln.line_total_excl_tax for ln in lines), Decimal("0"))
    sum_tax = sum((ln.tax_amount for ln in lines), Decimal("0"))
    inv.subtotal_excl_tax = sum_excl + (Decimal("5") if subtotal_inconsistent else Decimal("0"))
    inv.tax_amount = sum_tax + (Decimal("5") if sst_inconsistent else Decimal("0"))
    inv.total_incl_tax = inv.subtotal_excl_tax + inv.tax_amount
    inv.discount_amount = Decimal("0")
    inv.base_currency_amount = inv.total_incl_tax
    inv.precheck_result = None
    inv.precheck_at = None
    return inv


def _stub_persist():
    """Patch the AICallLog persistence so tests don't try a real DB session."""
    return patch.object(svc, "_persist_ai_call_log", new=AsyncMock())


def _stub_to_detail():
    """The mapper requires a real Invoice; we just want to assert through it."""
    return patch.object(svc, "_to_detail", new=lambda inv: inv)


# ── Pure-function tests (hard rules + helpers) ───────────────────────────────


def test_is_valid_tin_accepts_known_formats():
    assert svc._is_valid_tin("C1234567890")
    assert svc._is_valid_tin("IG1234567890")
    assert svc._is_valid_tin("EI00000000010")
    assert svc._is_valid_tin("123456789012")  # 12 digits
    assert not svc._is_valid_tin("")
    assert not svc._is_valid_tin(None)
    assert not svc._is_valid_tin("X12345")


def test_overall_status_three_tier():
    pass_only = [svc.PrecheckItem(
        code="X", category="hard", severity="ERROR", passed=True, message="ok",
    )]
    assert svc._overall_status(pass_only) == "PASS"

    warn_only = [svc.PrecheckItem(
        code="X", category="soft", severity="WARN", passed=False, message="warn",
    )]
    assert svc._overall_status(warn_only) == "WARN"

    fail_mixed = [
        svc.PrecheckItem(code="X", category="soft", severity="WARN", passed=False, message="w"),
        svc.PrecheckItem(code="Y", category="hard", severity="ERROR", passed=False, message="e"),
    ]
    assert svc._overall_status(fail_mixed) == "FAIL"


def test_run_hard_rules_happy_path_all_pass():
    inv = _make_inv()
    items = svc.run_hard_rules(inv)
    assert len(items) == 7
    assert all(it.category == "hard" for it in items)
    failed = [it for it in items if not it.passed]
    assert failed == [], f"Unexpected hard failures: {[it.code for it in failed]}"


def test_run_hard_rules_sst_mismatch_flags_consistency():
    inv = _make_inv(sst_inconsistent=True)
    items = svc.run_hard_rules(inv)
    failed = {it.code: it for it in items if not it.passed}
    assert "SST_TAX_AMOUNT_CONSISTENT" in failed
    # Other hard rules still pass.
    assert "SELLER_TIN_FORMAT" not in failed
    assert "MSIC_CODE_PRESENT" not in failed


def test_run_hard_rules_b2b_buyer_missing_tin():
    inv = _make_inv(buyer_tin="", buyer_type=CustomerType.B2B)
    items = svc.run_hard_rules(inv)
    failed = {it.code: it for it in items if not it.passed}
    assert "BUYER_TIN_PRESENT_OR_B2C" in failed


def test_run_hard_rules_b2c_empty_tin_passes():
    inv = _make_inv(buyer_tin="", buyer_type=CustomerType.B2C, buyer_name="Walk-in Customer")
    items = svc.run_hard_rules(inv)
    failed = {it.code: it for it in items if not it.passed}
    assert "BUYER_TIN_PRESENT_OR_B2C" not in failed


def test_run_hard_rules_invalid_sst_rate_flags():
    inv = _make_inv(line_tax_rates=(Decimal("7.00"),))
    items = svc.run_hard_rules(inv)
    failed = {it.code: it for it in items if not it.passed}
    assert "SST_RATE_VALID" in failed


def test_run_hard_rules_foreign_currency_zero_rate_flags():
    inv = _make_inv(currency="USD", exchange_rate=Decimal("0"))
    items = svc.run_hard_rules(inv)
    failed = {it.code: it for it in items if not it.passed}
    assert "CURRENCY_RATE_PRESENT" in failed


# ── Service-level tests ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_precheck_invoice_not_found_raises():
    session = make_mock_session()
    user = make_mock_user(role=RoleCode.SALES)

    inv_repo = MagicMock()
    inv_repo.get_detail = AsyncMock(return_value=None)

    with patch.object(svc, "InvoiceRepository", return_value=inv_repo):
        with pytest.raises(NotFoundError) as exc:
            await svc.precheck_invoice(session, invoice_id=999, org_id=1, user=user)
    assert exc.value.error_code == "INVOICE_NOT_FOUND"


@pytest.mark.asyncio
async def test_precheck_with_ai_disabled_degrades_soft_to_pass():
    session = make_mock_session()
    user = make_mock_user(role=RoleCode.SALES)
    inv = _make_inv()

    inv_repo = MagicMock()
    inv_repo.get_detail = AsyncMock(return_value=inv)
    gate = AsyncMock(return_value=False)

    with (
        patch.object(svc, "InvoiceRepository", return_value=inv_repo),
        patch.object(svc.AIFeatureGate, "is_enabled", new=gate),
        _stub_persist(),
        _stub_to_detail(),
    ):
        result = await svc.precheck_invoice(session, invoice_id=5, org_id=1, user=user)

    assert inv.precheck_result is not None
    pr = inv.precheck_result
    assert pr["ai_used"] is False
    assert pr["ai_error"] == "AI_FEATURE_DISABLED"
    assert pr["overall_status"] == "PASS"
    soft_items = [it for it in pr["items"] if it["category"] == "soft"]
    assert len(soft_items) == 3
    assert all(it["passed"] for it in soft_items)
    assert result is inv  # _to_detail stub passes through.


@pytest.mark.asyncio
async def test_precheck_with_llm_timeout_degrades_softly():
    session = make_mock_session()
    user = make_mock_user(role=RoleCode.SALES)
    inv = _make_inv()

    inv_repo = MagicMock()
    inv_repo.get_detail = AsyncMock(return_value=inv)
    gate = AsyncMock(return_value=True)

    timeout_stats = svc._SoftCallStats(
        status=AICallStatus.TIMEOUT,
        error_code="LLM_TIMEOUT",
        input_tokens=0,
        output_tokens=0,
        latency_ms=3001,
        model="claude-haiku-4-5-20251001",
        prompt_version="1.0.0",
    )
    soft_items = svc._degraded_soft_items("AI timeout")
    fake_ai = MagicMock()
    fake_ai.call_soft_rules = AsyncMock(return_value=(soft_items, timeout_stats))

    with (
        patch.object(svc, "InvoiceRepository", return_value=inv_repo),
        patch.object(svc.AIFeatureGate, "is_enabled", new=gate),
        patch.object(svc, "precheck_ai_service", new=fake_ai),
        _stub_persist(),
        _stub_to_detail(),
    ):
        await svc.precheck_invoice(session, invoice_id=5, org_id=1, user=user)

    pr = inv.precheck_result
    assert pr["ai_used"] is False
    assert pr["ai_error"] == "LLM_TIMEOUT"
    soft = [it for it in pr["items"] if it["category"] == "soft"]
    assert len(soft) == 3
    assert all(it["passed"] for it in soft)


@pytest.mark.asyncio
async def test_precheck_with_llm_success_marks_ai_used():
    session = make_mock_session()
    user = make_mock_user(role=RoleCode.SALES)
    inv = _make_inv()

    inv_repo = MagicMock()
    inv_repo.get_detail = AsyncMock(return_value=inv)
    gate = AsyncMock(return_value=True)

    success_stats = svc._SoftCallStats(
        status=AICallStatus.SUCCESS,
        error_code=None,
        input_tokens=120,
        output_tokens=85,
        latency_ms=820,
        model="claude-haiku-4-5-20251001",
        prompt_version="1.0.0",
    )
    soft_items = [
        svc.PrecheckItem(
            code="BUYER_NAME_VS_TYPE_LOOKS_CONSISTENT", category="soft",
            severity="INFO", passed=True, message="Name pattern consistent.",
        ),
        svc.PrecheckItem(
            code="LINE_DESCRIPTION_QUALITY", category="soft",
            severity="WARN", passed=False,
            message="Line 1 description is too generic.",
            suggestion="Use a specific product name.",
        ),
        svc.PrecheckItem(
            code="BUSINESS_DATE_REASONABLE", category="soft",
            severity="INFO", passed=True, message="Date is within reasonable window.",
        ),
    ]
    fake_ai = MagicMock()
    fake_ai.call_soft_rules = AsyncMock(return_value=(soft_items, success_stats))

    with (
        patch.object(svc, "InvoiceRepository", return_value=inv_repo),
        patch.object(svc.AIFeatureGate, "is_enabled", new=gate),
        patch.object(svc, "precheck_ai_service", new=fake_ai),
        _stub_persist(),
        _stub_to_detail(),
    ):
        await svc.precheck_invoice(session, invoice_id=5, org_id=1, user=user)

    pr = inv.precheck_result
    assert pr["ai_used"] is True
    assert pr["ai_error"] is None
    # Soft WARN failure → overall WARN (no hard ERROR failures).
    assert pr["overall_status"] == "WARN"
    soft = [it for it in pr["items"] if it["category"] == "soft"]
    assert len(soft) == 3
    assert any(it["code"] == "LINE_DESCRIPTION_QUALITY" and not it["passed"] for it in soft)


@pytest.mark.asyncio
async def test_precheck_persists_log_when_ai_disabled():
    """The DISABLED log row is essential for AI-cost observability."""
    session = make_mock_session()
    user = make_mock_user(role=RoleCode.SALES)
    inv = _make_inv()

    inv_repo = MagicMock()
    inv_repo.get_detail = AsyncMock(return_value=inv)
    gate = AsyncMock(return_value=False)
    persist_mock = AsyncMock()

    with (
        patch.object(svc, "InvoiceRepository", return_value=inv_repo),
        patch.object(svc.AIFeatureGate, "is_enabled", new=gate),
        patch.object(svc, "_persist_ai_call_log", new=persist_mock),
        _stub_to_detail(),
    ):
        await svc.precheck_invoice(session, invoice_id=5, org_id=1, user=user)

    persist_mock.assert_awaited_once()
    kwargs = persist_mock.await_args.kwargs
    assert kwargs["stats"].status == AICallStatus.DISABLED
    assert kwargs["stats"].error_code == "AI_FEATURE_DISABLED"


@pytest.mark.asyncio
async def test_precheck_overall_fail_when_hard_rule_fails():
    session = make_mock_session()
    user = make_mock_user(role=RoleCode.SALES)
    inv = _make_inv(sst_inconsistent=True)

    inv_repo = MagicMock()
    inv_repo.get_detail = AsyncMock(return_value=inv)
    gate = AsyncMock(return_value=False)

    with (
        patch.object(svc, "InvoiceRepository", return_value=inv_repo),
        patch.object(svc.AIFeatureGate, "is_enabled", new=gate),
        _stub_persist(),
        _stub_to_detail(),
    ):
        await svc.precheck_invoice(session, invoice_id=5, org_id=1, user=user)

    pr = inv.precheck_result
    assert pr["overall_status"] == "FAIL"
    assert any(
        it["code"] == "SST_TAX_AMOUNT_CONSISTENT" and not it["passed"]
        for it in pr["items"]
    )
