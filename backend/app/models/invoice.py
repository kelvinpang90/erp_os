from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    func,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.enums import (
    CreditNoteReason,
    CreditNoteStatus,
    InvoiceStatus,
    InvoiceType,
    PaymentDirection,
    PaymentMethod,
    RejectedBy,
)
from app.models.base import Base, SoftDeleteMixin, TimestampedMixin, VersionedMixin

if TYPE_CHECKING:
    from app.models.organization import Organization, User, Warehouse
    from app.models.partner import Customer, Supplier
    from app.models.sales import SalesOrder, SalesOrderLine
    from app.models.sku import SKU
    from app.models.master import UOM, TaxRate
    from app.models.audit import UploadedFile
    from app.models.purchase import PurchaseOrder
    from app.models.stock import StockMovement


class Invoice(Base, SoftDeleteMixin, TimestampedMixin, VersionedMixin):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("organization_id", "document_no", name="uq_inv_org_document_no"),
        UniqueConstraint("uin", name="uq_inv_uin"),
        Index("ix_inv_org_status_date", "organization_id", "status", "business_date"),
        Index("ix_inv_so", "sales_order_id"),
        Index("ix_inv_customer", "customer_id"),
        Index("ix_inv_validated_at", "status", "validated_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", name="fk_inv_org"), nullable=False, index=True
    )
    document_no: Mapped[str] = mapped_column(String(32), nullable=False)
    invoice_type: Mapped[InvoiceType] = mapped_column(
        Enum(InvoiceType, name="invoicetype"), nullable=False, default=InvoiceType.INVOICE
    )
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus, name="invoicestatus"), nullable=False, default=InvoiceStatus.DRAFT
    )
    sales_order_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("sales_orders.id", name="fk_inv_so"), nullable=True
    )
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customers.id", name="fk_inv_customer"), nullable=False
    )
    warehouse_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("warehouses.id", name="fk_inv_warehouse"), nullable=True
    )
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="MYR")
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=1)
    subtotal_excl_tax: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    total_incl_tax: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    base_currency_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    uin: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    qr_code_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    validated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    finalized_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    rejected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    rejected_by: Mapped[Optional[RejectedBy]] = mapped_column(
        Enum(RejectedBy, name="rejectedby"), nullable=True
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    rejection_attachment_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("uploaded_files.id", name="fk_inv_rejection_attachment"), nullable=True
    )
    precheck_result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    precheck_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pdf_file_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("uploaded_files.id", name="fk_inv_pdf_file"), nullable=True
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", name="fk_inv_created_by"), nullable=True
    )
    updated_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", name="fk_inv_updated_by"), nullable=True
    )

    organization: Mapped["Organization"] = relationship("Organization")
    sales_order: Mapped[Optional["SalesOrder"]] = relationship("SalesOrder")
    customer: Mapped["Customer"] = relationship("Customer")
    warehouse: Mapped[Optional["Warehouse"]] = relationship("Warehouse")
    lines: Mapped[List["InvoiceLine"]] = relationship(
        "InvoiceLine", back_populates="invoice", cascade="all, delete-orphan"
    )
    credit_notes: Mapped[List["CreditNote"]] = relationship("CreditNote", back_populates="invoice")
    payment_allocations: Mapped[List["PaymentAllocation"]] = relationship(
        "PaymentAllocation", back_populates="invoice"
    )
    rejection_attachment: Mapped[Optional["UploadedFile"]] = relationship(
        "UploadedFile", foreign_keys=[rejection_attachment_id]
    )
    pdf_file: Mapped[Optional["UploadedFile"]] = relationship(
        "UploadedFile", foreign_keys=[pdf_file_id]
    )
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])
    updater: Mapped[Optional["User"]] = relationship("User", foreign_keys=[updated_by])


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"
    __table_args__ = (
        UniqueConstraint("invoice_id", "line_no", name="uq_invl_inv_lineno"),
        Index("ix_invl_sol", "sales_order_line_id"),
        Index("ix_invl_sku", "sku_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("invoices.id", name="fk_invl_inv", ondelete="CASCADE"), nullable=False
    )
    sales_order_line_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("sales_order_lines.id", name="fk_invl_sol"), nullable=True
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    sku_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("skus.id", name="fk_invl_sku"), nullable=False
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    uom_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("uoms.id", name="fk_invl_uom"), nullable=False
    )
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price_excl_tax: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    tax_rate_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tax_rates.id", name="fk_invl_tax"), nullable=False
    )
    tax_rate_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    line_total_excl_tax: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    line_total_incl_tax: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    msic_code: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.current_timestamp()
    )

    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="lines")
    sales_order_line: Mapped[Optional["SalesOrderLine"]] = relationship("SalesOrderLine")
    sku: Mapped["SKU"] = relationship("SKU")
    uom: Mapped["UOM"] = relationship("UOM")
    tax_rate: Mapped["TaxRate"] = relationship("TaxRate")
    credit_note_lines: Mapped[List["CreditNoteLine"]] = relationship(
        "CreditNoteLine", back_populates="invoice_line"
    )


class CreditNote(Base, SoftDeleteMixin, TimestampedMixin, VersionedMixin):
    __tablename__ = "credit_notes"
    __table_args__ = (
        UniqueConstraint("organization_id", "document_no", name="uq_cn_org_document_no"),
        Index("ix_cn_org_status_date", "organization_id", "status", "business_date"),
        Index("ix_cn_invoice", "invoice_id"),
        Index("ix_cn_customer", "customer_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", name="fk_cn_org"), nullable=False, index=True
    )
    document_no: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[CreditNoteStatus] = mapped_column(
        Enum(CreditNoteStatus, name="creditnotestatus"), nullable=False, default=CreditNoteStatus.DRAFT
    )
    invoice_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("invoices.id", name="fk_cn_invoice"), nullable=False
    )
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customers.id", name="fk_cn_customer"), nullable=False
    )
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[CreditNoteReason] = mapped_column(
        Enum(CreditNoteReason, name="creditnotereason"), nullable=False
    )
    reason_description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="MYR")
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=1)
    subtotal_excl_tax: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    total_incl_tax: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    base_currency_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    uin: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    qr_code_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    validated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    finalized_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    rejected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pdf_file_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("uploaded_files.id", name="fk_cn_pdf_file"), nullable=True
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", name="fk_cn_created_by"), nullable=True
    )
    updated_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", name="fk_cn_updated_by"), nullable=True
    )

    organization: Mapped["Organization"] = relationship("Organization")
    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="credit_notes")
    customer: Mapped["Customer"] = relationship("Customer")
    lines: Mapped[List["CreditNoteLine"]] = relationship(
        "CreditNoteLine", back_populates="credit_note", cascade="all, delete-orphan"
    )
    payment_allocations: Mapped[List["PaymentAllocation"]] = relationship(
        "PaymentAllocation", back_populates="credit_note"
    )
    pdf_file: Mapped[Optional["UploadedFile"]] = relationship("UploadedFile", foreign_keys=[pdf_file_id])
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])
    updater: Mapped[Optional["User"]] = relationship("User", foreign_keys=[updated_by])


class CreditNoteLine(Base):
    __tablename__ = "credit_note_lines"
    __table_args__ = (
        UniqueConstraint("credit_note_id", "line_no", name="uq_cnl_cn_lineno"),
        Index("ix_cnl_invl", "invoice_line_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    credit_note_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("credit_notes.id", name="fk_cnl_cn", ondelete="CASCADE"), nullable=False
    )
    invoice_line_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("invoice_lines.id", name="fk_cnl_invl"), nullable=False
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    sku_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("skus.id", name="fk_cnl_sku"), nullable=False
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    uom_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("uoms.id", name="fk_cnl_uom"), nullable=False
    )
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price_excl_tax: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    tax_rate_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    line_total_excl_tax: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    line_total_incl_tax: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    snapshot_avg_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.current_timestamp()
    )

    credit_note: Mapped["CreditNote"] = relationship("CreditNote", back_populates="lines")
    invoice_line: Mapped["InvoiceLine"] = relationship("InvoiceLine", back_populates="credit_note_lines")
    sku: Mapped["SKU"] = relationship("SKU")
    uom: Mapped["UOM"] = relationship("UOM")


class Payment(Base, SoftDeleteMixin, TimestampedMixin, VersionedMixin):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("organization_id", "document_no", name="uq_pay_org_document_no"),
        Index("ix_pay_customer", "customer_id"),
        Index("ix_pay_supplier", "supplier_id"),
        Index("ix_pay_org_date", "organization_id", "business_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", name="fk_pay_org"), nullable=False, index=True
    )
    document_no: Mapped[str] = mapped_column(String(32), nullable=False)
    direction: Mapped[PaymentDirection] = mapped_column(
        Enum(PaymentDirection, name="paymentdirection"), nullable=False
    )
    customer_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("customers.id", name="fk_pay_customer"), nullable=True
    )
    supplier_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("suppliers.id", name="fk_pay_supplier"), nullable=True
    )
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, name="paymentmethod"), nullable=False
    )
    reference_no: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="MYR")
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=1)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    base_currency_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    allocated_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    unallocated_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", name="fk_pay_created_by"), nullable=True
    )

    organization: Mapped["Organization"] = relationship("Organization")
    customer: Mapped[Optional["Customer"]] = relationship("Customer")
    supplier: Mapped[Optional["Supplier"]] = relationship("Supplier")
    allocations: Mapped[List["PaymentAllocation"]] = relationship(
        "PaymentAllocation", back_populates="payment", cascade="all, delete-orphan"
    )
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])


class PaymentAllocation(Base):
    __tablename__ = "payment_allocations"
    __table_args__ = (
        Index("ix_palloc_payment", "payment_id"),
        Index("ix_palloc_invoice", "invoice_id"),
        Index("ix_palloc_po", "purchase_order_id"),
        Index("ix_palloc_cn", "credit_note_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    payment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("payments.id", name="fk_palloc_payment", ondelete="CASCADE"), nullable=False
    )
    invoice_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("invoices.id", name="fk_palloc_invoice"), nullable=True
    )
    purchase_order_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("purchase_orders.id", name="fk_palloc_po"), nullable=True
    )
    credit_note_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("credit_notes.id", name="fk_palloc_cn"), nullable=True
    )
    allocated_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    allocated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.current_timestamp()
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", name="fk_palloc_created_by"), nullable=True
    )

    payment: Mapped["Payment"] = relationship("Payment", back_populates="allocations")
    invoice: Mapped[Optional["Invoice"]] = relationship("Invoice", back_populates="payment_allocations")
    purchase_order: Mapped[Optional["PurchaseOrder"]] = relationship("PurchaseOrder")
    credit_note: Mapped[Optional["CreditNote"]] = relationship("CreditNote", back_populates="payment_allocations")
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])
