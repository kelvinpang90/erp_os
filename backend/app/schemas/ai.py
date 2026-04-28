"""
Pydantic DTOs for AI endpoints.

OCR result models mirror what the LLM is asked to produce in
``prompts/ocr_invoice.yaml`` — keep them in sync. The frontend uses
``OCRPurchaseOrder`` to pre-fill the PO create form.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

_decimal_cfg = ConfigDict(json_encoders={Decimal: str})


# ── OCR — Purchase Order extraction ──────────────────────────────────────────

class OCRLine(BaseModel):
    description: str = Field(..., max_length=500)
    sku_code: Optional[str] = Field(None, max_length=64)
    qty: Decimal = Field(..., ge=Decimal("0"))
    uom: Optional[str] = Field(None, max_length=32)
    unit_price_excl_tax: Decimal = Field(..., ge=Decimal("0"))
    tax_rate_percent: Optional[Decimal] = Field(None, ge=Decimal("0"), le=Decimal("100"))
    discount_percent: Optional[Decimal] = Field(None, ge=Decimal("0"), le=Decimal("100"))

    model_config = _decimal_cfg


class OCRPurchaseOrder(BaseModel):
    supplier_name: Optional[str] = Field(None, max_length=200)
    supplier_tin: Optional[str] = Field(None, max_length=32)
    supplier_address: Optional[str] = Field(None, max_length=500)
    invoice_no: Optional[str] = Field(None, max_length=64)
    business_date: Optional[date] = None
    currency: Optional[str] = Field(None, max_length=8)
    subtotal_excl_tax: Optional[Decimal] = Field(None, ge=Decimal("0"))
    tax_amount: Optional[Decimal] = Field(None, ge=Decimal("0"))
    total_incl_tax: Optional[Decimal] = Field(None, ge=Decimal("0"))
    lines: list[OCRLine] = Field(default_factory=list)
    remarks: Optional[str] = None
    confidence: Literal["high", "medium", "low"] = "medium"

    model_config = _decimal_cfg


# ── SSE event payloads ───────────────────────────────────────────────────────

class OCRProgressEvent(BaseModel):
    stage: Literal["uploaded", "calling_ai", "parsing", "done", "error"]
    progress: int = Field(..., ge=0, le=100)
    message: Optional[str] = None


class OCRErrorEvent(BaseModel):
    code: str
    message: str
