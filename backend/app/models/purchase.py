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
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.enums import POSource, POStatus
from app.models.base import Base, SoftDeleteMixin, TimestampedMixin, VersionedMixin

if TYPE_CHECKING:
    from app.models.organization import Organization, User, Warehouse
    from app.models.partner import Supplier
    from app.models.sku import SKU
    from app.models.master import UOM, TaxRate
    from app.models.audit import UploadedFile


class PurchaseOrder(Base, SoftDeleteMixin, TimestampedMixin, VersionedMixin):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        UniqueConstraint("organization_id", "document_no", name="uq_po_org_document_no"),
        Index("ix_po_org_status_date", "organization_id", "status", "business_date"),
        Index("ix_po_supplier", "supplier_id"),
        Index("ix_po_warehouse", "warehouse_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", name="fk_po_org"), nullable=False, index=True
    )
    document_no: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[POStatus] = mapped_column(
        Enum(POStatus, name="postatus"), nullable=False, default=POStatus.DRAFT
    )
    supplier_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("suppliers.id", name="fk_po_supplier"), nullable=False
    )
    warehouse_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("warehouses.id", name="fk_po_warehouse"), nullable=False
    )
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="MYR")
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=1)
    subtotal_excl_tax: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    shipping_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    total_incl_tax: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    base_currency_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    payment_terms_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cancel_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    source: Mapped[POSource] = mapped_column(
        Enum(POSource, name="posource"), nullable=False, default=POSource.MANUAL
    )
    source_file_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("uploaded_files.id", name="fk_po_source_file"), nullable=True
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", name="fk_po_created_by"), nullable=True
    )
    updated_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", name="fk_po_updated_by"), nullable=True
    )

    organization: Mapped["Organization"] = relationship("Organization")
    supplier: Mapped["Supplier"] = relationship("Supplier")
    warehouse: Mapped["Warehouse"] = relationship("Warehouse")
    lines: Mapped[List["PurchaseOrderLine"]] = relationship(
        "PurchaseOrderLine", back_populates="purchase_order", cascade="all, delete-orphan"
    )
    goods_receipts: Mapped[List["GoodsReceipt"]] = relationship("GoodsReceipt", back_populates="purchase_order")
    source_file: Mapped[Optional["UploadedFile"]] = relationship("UploadedFile", foreign_keys=[source_file_id])
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])
    updater: Mapped[Optional["User"]] = relationship("User", foreign_keys=[updated_by])


class PurchaseOrderLine(Base, TimestampedMixin):
    __tablename__ = "purchase_order_lines"
    __table_args__ = (
        UniqueConstraint("purchase_order_id", "line_no", name="uq_pol_po_lineno"),
        Index("ix_pol_sku", "sku_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    purchase_order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("purchase_orders.id", name="fk_pol_po", ondelete="CASCADE"), nullable=False
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    sku_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("skus.id", name="fk_pol_sku"), nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    uom_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("uoms.id", name="fk_pol_uom"), nullable=False
    )
    qty_ordered: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    qty_received: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    unit_price_excl_tax: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    tax_rate_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tax_rates.id", name="fk_pol_tax"), nullable=False
    )
    tax_rate_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    line_total_excl_tax: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    line_total_incl_tax: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    batch_no: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    purchase_order: Mapped["PurchaseOrder"] = relationship("PurchaseOrder", back_populates="lines")
    sku: Mapped["SKU"] = relationship("SKU")
    uom: Mapped["UOM"] = relationship("UOM")
    tax_rate: Mapped["TaxRate"] = relationship("TaxRate")
    receipt_lines: Mapped[List["GoodsReceiptLine"]] = relationship(
        "GoodsReceiptLine", back_populates="purchase_order_line"
    )


class GoodsReceipt(Base, SoftDeleteMixin, TimestampedMixin):
    __tablename__ = "goods_receipts"
    __table_args__ = (
        UniqueConstraint("organization_id", "document_no", name="uq_gr_org_document_no"),
        Index("ix_gr_po", "purchase_order_id"),
        Index("ix_gr_org_date", "organization_id", "receipt_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", name="fk_gr_org"), nullable=False, index=True
    )
    document_no: Mapped[str] = mapped_column(String(32), nullable=False)
    purchase_order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("purchase_orders.id", name="fk_gr_po"), nullable=False
    )
    warehouse_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("warehouses.id", name="fk_gr_warehouse"), nullable=False
    )
    receipt_date: Mapped[date] = mapped_column(Date, nullable=False)
    delivery_note_no: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    received_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", name="fk_gr_received_by"), nullable=True
    )
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", name="fk_gr_created_by"), nullable=True
    )

    organization: Mapped["Organization"] = relationship("Organization")
    purchase_order: Mapped["PurchaseOrder"] = relationship("PurchaseOrder", back_populates="goods_receipts")
    warehouse: Mapped["Warehouse"] = relationship("Warehouse")
    receiver: Mapped[Optional["User"]] = relationship("User", foreign_keys=[received_by])
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])
    lines: Mapped[List["GoodsReceiptLine"]] = relationship(
        "GoodsReceiptLine", back_populates="goods_receipt", cascade="all, delete-orphan"
    )


class GoodsReceiptLine(Base):
    __tablename__ = "goods_receipt_lines"
    __table_args__ = (
        Index("ix_grl_gr", "goods_receipt_id"),
        Index("ix_grl_pol", "purchase_order_line_id"),
        Index("ix_grl_sku", "sku_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goods_receipt_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("goods_receipts.id", name="fk_grl_gr", ondelete="CASCADE"), nullable=False
    )
    purchase_order_line_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("purchase_order_lines.id", name="fk_grl_pol"), nullable=False
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    sku_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("skus.id", name="fk_grl_sku"), nullable=False
    )
    uom_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("uoms.id", name="fk_grl_uom"), nullable=False
    )
    qty_received: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    batch_no: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    remarks: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.current_timestamp()
    )

    goods_receipt: Mapped["GoodsReceipt"] = relationship("GoodsReceipt", back_populates="lines")
    purchase_order_line: Mapped["PurchaseOrderLine"] = relationship(
        "PurchaseOrderLine", back_populates="receipt_lines"
    )
    sku: Mapped["SKU"] = relationship("SKU")
    uom: Mapped["UOM"] = relationship("UOM")
