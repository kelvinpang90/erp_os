"""Pydantic schemas for the Invoice (e-Invoice) module — Window 11."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.enums import InvoiceStatus, InvoiceType, RejectedBy

_decimal_cfg = ConfigDict(from_attributes=True, json_encoders={Decimal: str})


# ── Inputs ───────────────────────────────────────────────────────────────────


class GenerateFromSOIn(BaseModel):
    """Input for POST /sales-orders/{id}/generate-invoice.

    business_date / due_date are optional — defaults to today / today+30 days
    if not provided. Window 11 uses the SO's currency, exchange rate and
    customer; no overrides exposed.
    """

    business_date: Optional[date] = None
    due_date: Optional[date] = None
    remarks: Optional[str] = None


class RejectByBuyerIn(BaseModel):
    """Input for POST /invoices/{id}/reject (buyer reject within 72h)."""

    reason: str = Field(..., min_length=3, max_length=1000)
    rejection_attachment_id: Optional[int] = None


# ── Line response ────────────────────────────────────────────────────────────


class InvoiceLineResponse(BaseModel):
    id: int
    line_no: int
    sales_order_line_id: Optional[int]
    sku_id: int
    sku_code: str = ""
    sku_name: str = ""
    description: str
    uom_id: int
    uom_code: str = ""
    qty: Decimal
    unit_price_excl_tax: Decimal
    tax_rate_id: int
    tax_rate_percent: Decimal
    tax_amount: Decimal
    discount_amount: Decimal
    line_total_excl_tax: Decimal
    line_total_incl_tax: Decimal
    msic_code: Optional[str]

    model_config = _decimal_cfg


# ── Header response ──────────────────────────────────────────────────────────


class InvoiceListItem(BaseModel):
    """Slim row for list pages."""

    id: int
    organization_id: int
    document_no: str
    invoice_type: InvoiceType
    status: InvoiceStatus
    sales_order_id: Optional[int]
    sales_order_no: str = ""
    customer_id: int
    customer_name: str = ""
    business_date: date
    due_date: Optional[date]
    currency: str
    total_incl_tax: Decimal
    paid_amount: Decimal
    seller_tin: Optional[str] = None
    buyer_tin: Optional[str] = None
    uin: Optional[str]
    submitted_at: Optional[datetime]
    validated_at: Optional[datetime]
    finalized_at: Optional[datetime]
    rejected_at: Optional[datetime]
    created_at: datetime

    model_config = _decimal_cfg


class InvoiceDetail(InvoiceListItem):
    warehouse_id: Optional[int]
    warehouse_name: str = ""
    exchange_rate: Decimal
    subtotal_excl_tax: Decimal
    tax_amount: Decimal
    discount_amount: Decimal
    base_currency_amount: Decimal
    qr_code_url: Optional[str]
    rejected_by: Optional[RejectedBy]
    rejection_reason: Optional[str]
    rejection_attachment_id: Optional[int]
    precheck_result: Optional[dict]
    precheck_at: Optional[datetime]
    remarks: Optional[str]
    # Server-computed convenience fields for the UI countdown.
    finalize_window_seconds: int = 0       # 72 (DEMO) or 259200 (prod)
    seconds_until_finalize: Optional[int] = None  # None unless status==VALIDATED
    lines: List[InvoiceLineResponse] = []

    model_config = _decimal_cfg


class FinalizeScanResult(BaseModel):
    """Response for POST /invoices/admin/run-finalize-scan."""

    finalized_count: int
    finalize_window_seconds: int


# ── Window 12: Consolidated invoice ──────────────────────────────────────────


class GenerateConsolidatedIn(BaseModel):
    """Request body for POST /invoices/admin/generate-monthly-consolidated."""

    year: int = Field(..., ge=2024, le=2100)
    month: int = Field(..., ge=1, le=12)


class ConsolidatedScanResult(BaseModel):
    """Response for the monthly consolidated batch job."""

    generated_count: int
    customer_ids: List[int]
    invoice_ids: List[int]
    year: int
    month: int
