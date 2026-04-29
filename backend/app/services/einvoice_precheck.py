"""e-Invoice precheck service — Window 12.

Runs a 10-item compliance checklist against a DRAFT Invoice before submitting
to MyInvois:

* 7 hard rules — pure code, never fail (TIN format, SST math, required fields,
  rate values, line/header consistency, MSIC presence, currency/rate sanity).
* 3 soft rules — Claude Haiku call, gated by ``AIFeatureGate``, ``asyncio.wait_for``
  with a 3s timeout. On timeout / API error / parse error / gate-disabled the
  soft layer degrades to ``passed=True`` for all 3 items so the overall verdict
  is still meaningful and the user can keep working.

The result is serialised into ``invoice.precheck_result`` (JSON) plus
``invoice.precheck_at`` (datetime), then returned as an ``InvoiceDetail`` so the
frontend can render the checklist Modal directly off the response.

Each call writes one ``AICallLog`` row (status SUCCESS / FAILURE / TIMEOUT /
DISABLED) so we can keep observing AI cost / success rate alongside OCR.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional

import structlog
from anthropic import AsyncAnthropic
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.exceptions import NotFoundError
from app.core.logging import get_request_id
from app.enums import AICallStatus, AIFeature, CustomerType
from app.models.audit import AICallLog
from app.models.invoice import Invoice
from app.models.organization import User
from app.repositories.invoice import InvoiceRepository
from app.schemas.invoice import InvoiceDetail
from app.services.ai_gate import AIFeatureGate
from app.services.einvoice import _to_detail  # reuse the same response mapper
from app.services.prompts import load_prompt

log = structlog.get_logger(__name__)


# ── Pricing (mirrors ocr.py — keep in sync if you add a model) ───────────────


_PRICING_USD_PER_MTOK: dict[str, tuple[Decimal, Decimal]] = {
    "claude-sonnet-4-6": (Decimal("3.00"), Decimal("15.00")),
    "claude-opus-4-7": (Decimal("15.00"), Decimal("75.00")),
    "claude-haiku-4-5-20251001": (Decimal("0.80"), Decimal("4.00")),
}
_DEFAULT_PRICING: tuple[Decimal, Decimal] = (Decimal("3.00"), Decimal("15.00"))


def _calc_cost_usd(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    in_rate, out_rate = _PRICING_USD_PER_MTOK.get(model, _DEFAULT_PRICING)
    cost = (Decimal(input_tokens) * in_rate + Decimal(output_tokens) * out_rate) / Decimal(1_000_000)
    return cost.quantize(Decimal("0.000001"))


_JSON_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.MULTILINE)


def _strip_json_fences(text: str) -> str:
    return _JSON_FENCE_RE.sub("", text).strip()


# ── Result schema (serialised into invoice.precheck_result) ──────────────────


class PrecheckItem(BaseModel):
    code: str
    category: str  # "hard" | "soft"
    severity: str  # "INFO" | "WARN" | "ERROR"
    passed: bool
    message: str
    suggestion: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class PrecheckResult(BaseModel):
    version: str = "1.0.0"
    checked_at: datetime
    overall_status: str  # "PASS" | "WARN" | "FAIL"
    ai_used: bool
    ai_error: Optional[str] = None
    items: list[PrecheckItem]

    model_config = ConfigDict(extra="forbid")


# ── TIN format ────────────────────────────────────────────────────────────────


# Accept any one of:
#   C followed by 10 digits      → corporate (Sdn Bhd / Bhd)
#   IG followed by 10 digits     → government / institutional
#   EI followed by 8-10 digits   → "General Public" / consolidated buyer slot
#   12 digits                    → individual NRIC-derived TIN
_TIN_RE = re.compile(r"^(?:C\d{10}|IG\d{10}|EI\d{8,10}|\d{12})$")
_GENERAL_PUBLIC_TINS = frozenset({"EI00000000010", "000000000000"})


def _is_valid_tin(tin: Optional[str]) -> bool:
    if not tin:
        return False
    if tin in _GENERAL_PUBLIC_TINS:
        return True
    return bool(_TIN_RE.match(tin))


# ── Hard rules ────────────────────────────────────────────────────────────────


_VALID_SST_RATES = (Decimal("0"), Decimal("6"), Decimal("10"))
_TOLERANCE = Decimal("0.01")


def _quantize2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"))


def run_hard_rules(invoice: Invoice) -> list[PrecheckItem]:
    """7 deterministic rules. Pure function — never raises."""
    items: list[PrecheckItem] = []
    org = invoice.organization
    cust = invoice.customer
    lines = list(invoice.lines or [])

    # 1. SELLER_TIN_FORMAT
    seller_tin = (org.tin or "").strip() if org else ""
    if _is_valid_tin(seller_tin):
        items.append(PrecheckItem(
            code="SELLER_TIN_FORMAT", category="hard", severity="ERROR",
            passed=True, message=f"Seller TIN '{seller_tin}' is well-formed.",
        ))
    else:
        items.append(PrecheckItem(
            code="SELLER_TIN_FORMAT", category="hard", severity="ERROR",
            passed=False,
            message=f"Seller TIN '{seller_tin or '(empty)'}' does not match LHDN format.",
            suggestion="Update organization TIN to C##########, IG##########, or 12-digit NRIC TIN.",
        ))

    # 2. BUYER_TIN_PRESENT_OR_B2C
    buyer_tin = (cust.tin or "").strip() if cust else ""
    is_b2c = bool(cust and getattr(cust, "customer_type", None) == CustomerType.B2C)
    if is_b2c:
        # B2C may use a "General Public" placeholder; if a TIN is present it
        # must still parse. Empty / placeholder is fine.
        if not buyer_tin or buyer_tin in _GENERAL_PUBLIC_TINS or _is_valid_tin(buyer_tin):
            items.append(PrecheckItem(
                code="BUYER_TIN_PRESENT_OR_B2C", category="hard", severity="ERROR",
                passed=True, message="Buyer is B2C — TIN optional / placeholder accepted.",
            ))
        else:
            items.append(PrecheckItem(
                code="BUYER_TIN_PRESENT_OR_B2C", category="hard", severity="ERROR",
                passed=False,
                message=f"B2C buyer TIN '{buyer_tin}' is malformed.",
                suggestion="Either clear the TIN or use the General Public placeholder EI00000000010.",
            ))
    else:
        if _is_valid_tin(buyer_tin):
            items.append(PrecheckItem(
                code="BUYER_TIN_PRESENT_OR_B2C", category="hard", severity="ERROR",
                passed=True, message=f"B2B buyer TIN '{buyer_tin}' is well-formed.",
            ))
        else:
            items.append(PrecheckItem(
                code="BUYER_TIN_PRESENT_OR_B2C", category="hard", severity="ERROR",
                passed=False,
                message=f"B2B buyer must have a valid TIN; got '{buyer_tin or '(empty)'}'.",
                suggestion="Add buyer TIN on the Customer record (C##########).",
            ))

    # 3. MSIC_CODE_PRESENT (seller header + each line)
    seller_msic = (org.msic_code or "").strip() if org else ""
    line_msic_missing = [ln.line_no for ln in lines if not (ln.msic_code or "").strip()]
    if seller_msic and not line_msic_missing:
        items.append(PrecheckItem(
            code="MSIC_CODE_PRESENT", category="hard", severity="ERROR",
            passed=True,
            message=f"Seller MSIC '{seller_msic}' present and all lines tagged.",
        ))
    else:
        bits: list[str] = []
        if not seller_msic:
            bits.append("seller MSIC is empty")
        if line_msic_missing:
            bits.append(f"lines {line_msic_missing} missing MSIC")
        items.append(PrecheckItem(
            code="MSIC_CODE_PRESENT", category="hard", severity="ERROR",
            passed=False,
            message="MSIC code missing: " + "; ".join(bits) + ".",
            suggestion="Set MSIC on Organization and on every SKU; LHDN requires it on every invoice line.",
        ))

    # 4. SST_TAX_AMOUNT_CONSISTENT — sum(line.tax_amount) == invoice.tax_amount (±0.01)
    sum_line_tax = sum((ln.tax_amount for ln in lines), Decimal("0"))
    delta = abs(_quantize2(sum_line_tax) - _quantize2(invoice.tax_amount))
    if delta <= _TOLERANCE:
        items.append(PrecheckItem(
            code="SST_TAX_AMOUNT_CONSISTENT", category="hard", severity="ERROR",
            passed=True,
            message=f"Tax total {invoice.tax_amount} matches sum of line taxes.",
        ))
    else:
        items.append(PrecheckItem(
            code="SST_TAX_AMOUNT_CONSISTENT", category="hard", severity="ERROR",
            passed=False,
            message=(
                f"Header tax_amount {invoice.tax_amount} != sum of line taxes "
                f"{sum_line_tax} (delta {delta})."
            ),
            suggestion="Regenerate the invoice from the SO so totals are recomputed.",
        ))

    # 5. SST_RATE_VALID — every line's tax_rate_percent ∈ {0, 6, 10}
    invalid_rates = [
        (ln.line_no, ln.tax_rate_percent) for ln in lines
        if Decimal(ln.tax_rate_percent) not in _VALID_SST_RATES
    ]
    if not invalid_rates:
        items.append(PrecheckItem(
            code="SST_RATE_VALID", category="hard", severity="ERROR",
            passed=True,
            message="All line tax rates are valid Malaysian SST rates (0/6/10).",
        ))
    else:
        sample = invalid_rates[0]
        items.append(PrecheckItem(
            code="SST_RATE_VALID", category="hard", severity="ERROR",
            passed=False,
            message=(
                f"Line {sample[0]} has tax_rate_percent={sample[1]}, "
                "which is not a valid Malaysian SST rate."
            ),
            suggestion="Pick a TaxRate of 0% (Exempt), 6% (Service Tax), or 10% (Sales Tax).",
        ))

    # 6. LINE_TOTAL_CONSISTENT — sum(line.line_total_excl_tax) == invoice.subtotal_excl_tax
    sum_excl = sum((ln.line_total_excl_tax for ln in lines), Decimal("0"))
    delta_sub = abs(_quantize2(sum_excl) - _quantize2(invoice.subtotal_excl_tax))
    if delta_sub <= _TOLERANCE:
        items.append(PrecheckItem(
            code="LINE_TOTAL_CONSISTENT", category="hard", severity="ERROR",
            passed=True,
            message=f"Subtotal {invoice.subtotal_excl_tax} matches sum of line subtotals.",
        ))
    else:
        items.append(PrecheckItem(
            code="LINE_TOTAL_CONSISTENT", category="hard", severity="ERROR",
            passed=False,
            message=(
                f"Header subtotal {invoice.subtotal_excl_tax} != "
                f"sum of line subtotals {sum_excl} (delta {delta_sub})."
            ),
            suggestion="Regenerate the invoice from the SO so totals are recomputed.",
        ))

    # 7. CURRENCY_RATE_PRESENT — non-MYR must have exchange_rate > 0
    if invoice.currency == "MYR":
        items.append(PrecheckItem(
            code="CURRENCY_RATE_PRESENT", category="hard", severity="ERROR",
            passed=True,
            message="Currency is MYR — no exchange rate needed.",
        ))
    elif Decimal(invoice.exchange_rate) > 0:
        items.append(PrecheckItem(
            code="CURRENCY_RATE_PRESENT", category="hard", severity="ERROR",
            passed=True,
            message=f"Foreign-currency invoice ({invoice.currency}) has rate {invoice.exchange_rate}.",
        ))
    else:
        items.append(PrecheckItem(
            code="CURRENCY_RATE_PRESENT", category="hard", severity="ERROR",
            passed=False,
            message=(
                f"Currency is {invoice.currency} but exchange_rate is "
                f"{invoice.exchange_rate}. LHDN needs a positive rate."
            ),
            suggestion="Set the exchange rate on the SO before generating the invoice.",
        ))

    return items


# ── Soft-rules degraded fallback ──────────────────────────────────────────────


_SOFT_CODES = (
    "BUYER_NAME_VS_TYPE_LOOKS_CONSISTENT",
    "LINE_DESCRIPTION_QUALITY",
    "BUSINESS_DATE_REASONABLE",
)


def _degraded_soft_items(reason: str) -> list[PrecheckItem]:
    """When AI is off / down, return a passing placeholder for each soft check."""
    return [
        PrecheckItem(
            code=code,
            category="soft",
            severity="INFO",
            passed=True,
            message=f"AI check skipped ({reason}); hard rules still applied.",
            suggestion=None,
        )
        for code in _SOFT_CODES
    ]


# ── LLM call ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class _SoftCallStats:
    status: AICallStatus
    error_code: Optional[str]
    input_tokens: int
    output_tokens: int
    latency_ms: int
    model: str
    prompt_version: str


def _build_llm_payload(invoice: Invoice, today: date) -> dict[str, Any]:
    org = invoice.organization
    cust = invoice.customer
    seller = {
        "tin": (org.tin or "") if org else "",
        "name": org.name if org else "",
        "msic_code": (org.msic_code or "") if org else "",
    }
    buyer_type = (
        cust.customer_type.value
        if cust and getattr(cust, "customer_type", None) is not None
        else "B2B"
    )
    buyer = {
        "tin": (cust.tin or "") if cust else "",
        "name": cust.name if cust else "",
        "type": buyer_type,
        "msic_code": (cust.msic_code or "") if cust else "",
    }
    header = {
        "invoice_type": invoice.invoice_type.value,
        "business_date": invoice.business_date.isoformat(),
        "currency": invoice.currency,
        "exchange_rate": str(invoice.exchange_rate),
        "total_incl_tax": str(invoice.total_incl_tax),
    }
    lines = [
        {
            "line_no": ln.line_no,
            "description": ln.description,
            "qty": str(ln.qty),
            "unit_price_excl_tax": str(ln.unit_price_excl_tax),
            "tax_rate_percent": str(ln.tax_rate_percent),
        }
        for ln in (invoice.lines or [])
    ]
    return {
        "seller_json": json.dumps(seller, ensure_ascii=False),
        "buyer_json": json.dumps(buyer, ensure_ascii=False),
        "header_json": json.dumps(header, ensure_ascii=False),
        "lines_json": json.dumps(lines, ensure_ascii=False),
        "today_iso": today.isoformat(),
    }


class EInvoicePrecheckService:
    """Stateless wrapper around AsyncAnthropic — instance for DI in tests."""

    def __init__(self, client: Optional[AsyncAnthropic] = None) -> None:
        self._client = client or AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def call_soft_rules(
        self,
        invoice: Invoice,
        *,
        today: date,
    ) -> tuple[list[PrecheckItem], _SoftCallStats]:
        """Call Claude Haiku for the 3 soft-rule items. Always degrade gracefully."""
        prompt = load_prompt("einvoice_precheck")
        model = prompt.model
        rendered_user = prompt.render(**_build_llm_payload(invoice, today))

        started = time.monotonic()
        try:
            response = await asyncio.wait_for(
                self._client.messages.create(
                    model=model,
                    system=prompt.system,
                    temperature=prompt.temperature,
                    max_tokens=prompt.max_tokens,
                    messages=[{"role": "user", "content": rendered_user}],
                ),
                timeout=3.0,
            )
        except asyncio.TimeoutError:
            latency_ms = int((time.monotonic() - started) * 1000)
            log.warning("einvoice_precheck.soft_timeout", invoice_id=invoice.id)
            return (
                _degraded_soft_items("AI timeout"),
                _SoftCallStats(
                    status=AICallStatus.TIMEOUT,
                    error_code="LLM_TIMEOUT",
                    input_tokens=0,
                    output_tokens=0,
                    latency_ms=latency_ms,
                    model=model,
                    prompt_version=prompt.version,
                ),
            )
        except Exception as e:  # noqa: BLE001
            latency_ms = int((time.monotonic() - started) * 1000)
            log.warning("einvoice_precheck.soft_api_error", invoice_id=invoice.id, err=str(e))
            return (
                _degraded_soft_items("AI API error"),
                _SoftCallStats(
                    status=AICallStatus.FAILURE,
                    error_code="LLM_API_ERROR",
                    input_tokens=0,
                    output_tokens=0,
                    latency_ms=latency_ms,
                    model=model,
                    prompt_version=prompt.version,
                ),
            )

        latency_ms = int((time.monotonic() - started) * 1000)
        input_tokens = int(getattr(response.usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(response.usage, "output_tokens", 0) or 0)

        text_blocks = [b.text for b in response.content if getattr(b, "type", None) == "text"]
        if not text_blocks:
            log.warning("einvoice_precheck.empty_response", invoice_id=invoice.id)
            return (
                _degraded_soft_items("AI returned no text"),
                _SoftCallStats(
                    status=AICallStatus.FAILURE,
                    error_code="EMPTY_LLM_RESPONSE",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                    model=model,
                    prompt_version=prompt.version,
                ),
            )

        raw = _strip_json_fences("\n".join(text_blocks))
        try:
            payload = json.loads(raw)
            raw_items = payload.get("items", [])
            soft_items: list[PrecheckItem] = []
            seen_codes: set[str] = set()
            for raw_item in raw_items:
                code = str(raw_item.get("code", "")).strip()
                if code not in _SOFT_CODES:
                    continue  # ignore anything off-script
                seen_codes.add(code)
                soft_items.append(
                    PrecheckItem(
                        code=code,
                        category="soft",
                        severity=str(raw_item.get("severity", "INFO")).upper(),
                        passed=bool(raw_item.get("passed", True)),
                        message=str(raw_item.get("message", ""))[:240] or "(no detail)",
                        suggestion=(str(raw_item.get("suggestion") or "") or None),
                    )
                )
            # Backfill any code the model dropped.
            for code in _SOFT_CODES:
                if code not in seen_codes:
                    soft_items.append(PrecheckItem(
                        code=code, category="soft", severity="INFO",
                        passed=True, message="No issues detected.",
                    ))
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            log.warning("einvoice_precheck.soft_parse_error", invoice_id=invoice.id, err=str(e))
            return (
                _degraded_soft_items("AI response unparseable"),
                _SoftCallStats(
                    status=AICallStatus.FAILURE,
                    error_code="LLM_JSON_PARSE_ERROR",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                    model=model,
                    prompt_version=prompt.version,
                ),
            )

        return soft_items, _SoftCallStats(
            status=AICallStatus.SUCCESS,
            error_code=None,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            model=model,
            prompt_version=prompt.version,
        )


# Default singleton — overridden in tests by patching.
precheck_ai_service = EInvoicePrecheckService()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _overall_status(items: list[PrecheckItem]) -> str:
    has_error = any(it.severity == "ERROR" and not it.passed for it in items)
    if has_error:
        return "FAIL"
    has_warn = any(
        (it.severity == "WARN" and not it.passed)
        or (it.severity == "ERROR" and not it.passed)
        for it in items
    )
    if has_warn:
        return "WARN"
    return "PASS"


async def _persist_ai_call_log(
    *,
    user: User,
    stats: _SoftCallStats,
    invoice_id: int,
) -> None:
    """Best-effort log row in a fresh session (mirrors ocr.py pattern)."""
    async with AsyncSessionLocal() as log_session:
        try:
            log_session.add(
                AICallLog(
                    organization_id=user.organization_id,
                    user_id=user.id,
                    feature=AIFeature.EINVOICE_PRECHECK,
                    provider="anthropic",
                    model=stats.model,
                    endpoint=f"/api/invoices/{invoice_id}/precheck",
                    prompt_version=stats.prompt_version,
                    input_tokens=stats.input_tokens,
                    output_tokens=stats.output_tokens,
                    cost_usd=_calc_cost_usd(stats.model, stats.input_tokens, stats.output_tokens),
                    latency_ms=stats.latency_ms,
                    status=stats.status,
                    error_code=stats.error_code,
                    request_id=get_request_id() or None,
                    metadata_={"invoice_id": invoice_id},
                )
            )
            await log_session.commit()
        except Exception:  # noqa: BLE001 — never let logging failure mask the result
            await log_session.rollback()
            log.exception("einvoice_precheck.log_persist_failed", invoice_id=invoice_id)


# ── Public API ───────────────────────────────────────────────────────────────


async def precheck_invoice(
    session: AsyncSession,
    *,
    invoice_id: int,
    org_id: int,
    user: User,
) -> InvoiceDetail:
    """Run hard + soft rules, persist the result, return the updated detail.

    The invoice can be in any pre-FINAL status — we only block submit at the
    transition itself, not at precheck (so users can re-run precheck after
    fixing fields).
    """
    repo = InvoiceRepository(session)
    invoice = await repo.get_detail(org_id, invoice_id)
    if invoice is None:
        raise NotFoundError(
            message=f"Invoice {invoice_id} not found.",
            error_code="INVOICE_NOT_FOUND",
        )

    started = time.monotonic()

    hard_items = run_hard_rules(invoice)

    # Decide whether to call the LLM — three-layer gate.
    ai_enabled = await AIFeatureGate.is_enabled(
        session, AIFeature.EINVOICE_PRECHECK, org_id
    )

    soft_items: list[PrecheckItem]
    ai_used: bool
    ai_error: Optional[str]

    if not ai_enabled:
        soft_items = _degraded_soft_items("AI feature disabled")
        ai_used = False
        ai_error = "AI_FEATURE_DISABLED"
        # Still record a log row so the gate's effect is observable.
        await _persist_ai_call_log(
            user=user,
            stats=_SoftCallStats(
                status=AICallStatus.DISABLED,
                error_code="AI_FEATURE_DISABLED",
                input_tokens=0,
                output_tokens=0,
                latency_ms=0,
                model="",
                prompt_version="",
            ),
            invoice_id=invoice.id,
        )
    else:
        soft_items, stats = await precheck_ai_service.call_soft_rules(
            invoice, today=date.today()
        )
        ai_used = stats.status == AICallStatus.SUCCESS
        ai_error = stats.error_code if not ai_used else None
        await _persist_ai_call_log(user=user, stats=stats, invoice_id=invoice.id)

    items = hard_items + soft_items
    result = PrecheckResult(
        version="1.0.0",
        checked_at=_now(),
        overall_status=_overall_status(items),
        ai_used=ai_used,
        ai_error=ai_error,
        items=items,
    )

    invoice.precheck_result = result.model_dump(mode="json")
    invoice.precheck_at = result.checked_at
    invoice.updated_by = user.id
    session.add(invoice)
    await session.flush()

    log.info(
        "einvoice_precheck.done",
        invoice_id=invoice.id,
        overall_status=result.overall_status,
        ai_used=ai_used,
        latency_ms=int((time.monotonic() - started) * 1000),
    )

    full = await repo.get_detail(org_id, invoice.id)
    return _to_detail(full)
