"""Pydantic schemas for the Credit Note module — Window 12."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.enums import CreditNoteReason, CreditNoteStatus

_decimal_cfg = ConfigDict(from_attributes=True, json_encoders={Decimal: str})


# ── Inputs ───────────────────────────────────────────────────────────────────


class CreditNoteLineIn(BaseModel):
    """One line in a CN-create payload — references an InvoiceLine and the
    quantity being credited (<= remaining quantity on that invoice line)."""

    invoice_line_id: int
    qty: Decimal = Field(..., gt=0)
    description: Optional[str] = None  # default to invoice line description


class CreditNoteCreateIn(BaseModel):
    invoice_id: int
    reason: CreditNoteReason
    reason_description: Optional[str] = Field(default=None, max_length=500)
    business_date: Optional[date] = None
    remarks: Optional[str] = None
    lines: List[CreditNoteLineIn] = Field(..., min_length=1)


# ── Line response ────────────────────────────────────────────────────────────


class CreditNoteLineResponse(BaseModel):
    id: int
    line_no: int
    invoice_line_id: int
    sku_id: int
    sku_code: str = ""
    sku_name: str = ""
    description: str
    uom_id: int
    uom_code: str = ""
    qty: Decimal
    unit_price_excl_tax: Decimal
    tax_rate_percent: Decimal
    tax_amount: Decimal
    line_total_excl_tax: Decimal
    line_total_incl_tax: Decimal
    snapshot_avg_cost: Optional[Decimal]

    model_config = _decimal_cfg


# ── Header response ──────────────────────────────────────────────────────────


class CreditNoteListItem(BaseModel):
    id: int
    organization_id: int
    document_no: str
    status: CreditNoteStatus
    invoice_id: int
    invoice_no: str = ""
    customer_id: int
    customer_name: str = ""
    business_date: date
    reason: CreditNoteReason
    currency: str
    total_incl_tax: Decimal
    uin: Optional[str]
    submitted_at: Optional[datetime]
    validated_at: Optional[datetime]
    created_at: datetime

    model_config = _decimal_cfg


class CreditNoteDetail(CreditNoteListItem):
    reason_description: Optional[str]
    exchange_rate: Decimal
    subtotal_excl_tax: Decimal
    tax_amount: Decimal
    base_currency_amount: Decimal
    qr_code_url: Optional[str]
    rejection_reason: Optional[str]
    remarks: Optional[str]
    lines: List[CreditNoteLineResponse] = []

    model_config = _decimal_cfg
