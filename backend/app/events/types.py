"""
Three core domain events for the ERP event bus.

StockMovementOccurred   — any change to physical stock quantities
DocumentStatusChanged   — PO / SO / Invoice / CN status transition
EInvoiceValidated       — LHDN MyInvois validation result received
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.events.base import DomainEvent


@dataclass
class DocumentStatusChanged(DomainEvent):
    document_type: str = ""        # "PO" | "SO" | "INVOICE" | "CN" | "TRANSFER" | "ADJUSTMENT"
    document_id: int = 0
    document_no: str = ""
    old_status: str = ""
    new_status: str = ""
    organization_id: int = 0
    actor_user_id: int | None = None
    # Optional richer snapshots — services for the three audited tables
    # (PO/SO, Invoice, CreditNote) populate these for compliance/diff display.
    before: dict | None = None
    after: dict | None = None


@dataclass
class StockMovementOccurred(DomainEvent):
    organization_id: int = 0
    sku_id: int = 0
    warehouse_id: int = 0
    movement_type: str = ""        # StockMovementType value
    quantity: Decimal = field(default_factory=lambda: Decimal("0"))
    source_document_type: str = "" # StockMovementSourceType value
    source_document_id: int = 0


@dataclass
class EInvoiceValidated(DomainEvent):
    organization_id: int = 0
    invoice_id: int = 0
    invoice_no: str = ""
    uin: str = ""                  # LHDN Unique Invoice Number
    validated_at: str = ""         # ISO datetime string
