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

from app.enums import SOStatus
from app.models.base import Base, SoftDeleteMixin, TimestampedMixin, VersionedMixin

if TYPE_CHECKING:
    from app.models.organization import Organization, User, Warehouse
    from app.models.partner import Customer
    from app.models.sku import SKU
    from app.models.master import UOM, TaxRate


class SalesOrder(Base, SoftDeleteMixin, TimestampedMixin, VersionedMixin):
    __tablename__ = "sales_orders"
    __table_args__ = (
        UniqueConstraint("organization_id", "document_no", name="uq_so_org_document_no"),
        Index("ix_so_org_status_date", "organization_id", "status", "business_date"),
        Index("ix_so_customer", "customer_id"),
        Index("ix_so_warehouse", "warehouse_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", name="fk_so_org"), nullable=False, index=True
    )
    document_no: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[SOStatus] = mapped_column(
        Enum(SOStatus, name="sostatus"), nullable=False, default=SOStatus.DRAFT
    )
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customers.id", name="fk_so_customer"), nullable=False
    )
    warehouse_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("warehouses.id", name="fk_so_warehouse"), nullable=False
    )
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_ship_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="MYR")
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=1)
    subtotal_excl_tax: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    shipping_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    total_incl_tax: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    base_currency_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    payment_terms_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    shipping_address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cancel_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    fully_shipped_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", name="fk_so_created_by"), nullable=True
    )
    updated_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", name="fk_so_updated_by"), nullable=True
    )

    organization: Mapped["Organization"] = relationship("Organization")
    customer: Mapped["Customer"] = relationship("Customer")
    warehouse: Mapped["Warehouse"] = relationship("Warehouse")
    lines: Mapped[List["SalesOrderLine"]] = relationship(
        "SalesOrderLine", back_populates="sales_order", cascade="all, delete-orphan"
    )
    delivery_orders: Mapped[List["DeliveryOrder"]] = relationship("DeliveryOrder", back_populates="sales_order")
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])
    updater: Mapped[Optional["User"]] = relationship("User", foreign_keys=[updated_by])


class SalesOrderLine(Base, TimestampedMixin):
    __tablename__ = "sales_order_lines"
    __table_args__ = (
        UniqueConstraint("sales_order_id", "line_no", name="uq_sol_so_lineno"),
        Index("ix_sol_sku", "sku_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sales_order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sales_orders.id", name="fk_sol_so", ondelete="CASCADE"), nullable=False
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    sku_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("skus.id", name="fk_sol_sku"), nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    uom_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("uoms.id", name="fk_sol_uom"), nullable=False
    )
    qty_ordered: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    qty_shipped: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    qty_invoiced: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    unit_price_excl_tax: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    tax_rate_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tax_rates.id", name="fk_sol_tax"), nullable=False
    )
    tax_rate_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    line_total_excl_tax: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    line_total_incl_tax: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    snapshot_avg_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    batch_no: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    serial_no: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    sales_order: Mapped["SalesOrder"] = relationship("SalesOrder", back_populates="lines")
    sku: Mapped["SKU"] = relationship("SKU")
    uom: Mapped["UOM"] = relationship("UOM")
    tax_rate: Mapped["TaxRate"] = relationship("TaxRate")
    delivery_lines: Mapped[List["DeliveryOrderLine"]] = relationship(
        "DeliveryOrderLine", back_populates="sales_order_line"
    )


class DeliveryOrder(Base, SoftDeleteMixin, TimestampedMixin):
    __tablename__ = "delivery_orders"
    __table_args__ = (
        UniqueConstraint("organization_id", "document_no", name="uq_do_org_document_no"),
        Index("ix_do_so", "sales_order_id"),
        Index("ix_do_org_date", "organization_id", "delivery_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", name="fk_do_org"), nullable=False, index=True
    )
    document_no: Mapped[str] = mapped_column(String(32), nullable=False)
    sales_order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sales_orders.id", name="fk_do_so"), nullable=False
    )
    warehouse_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("warehouses.id", name="fk_do_warehouse"), nullable=False
    )
    delivery_date: Mapped[date] = mapped_column(Date, nullable=False)
    shipping_method: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    tracking_no: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    delivered_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", name="fk_do_delivered_by"), nullable=True
    )
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", name="fk_do_created_by"), nullable=True
    )

    organization: Mapped["Organization"] = relationship("Organization")
    sales_order: Mapped["SalesOrder"] = relationship("SalesOrder", back_populates="delivery_orders")
    warehouse: Mapped["Warehouse"] = relationship("Warehouse")
    deliverer: Mapped[Optional["User"]] = relationship("User", foreign_keys=[delivered_by])
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])
    lines: Mapped[List["DeliveryOrderLine"]] = relationship(
        "DeliveryOrderLine", back_populates="delivery_order", cascade="all, delete-orphan"
    )


class DeliveryOrderLine(Base):
    __tablename__ = "delivery_order_lines"
    __table_args__ = (
        Index("ix_dol_do", "delivery_order_id"),
        Index("ix_dol_sol", "sales_order_line_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    delivery_order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("delivery_orders.id", name="fk_dol_do", ondelete="CASCADE"), nullable=False
    )
    sales_order_line_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sales_order_lines.id", name="fk_dol_sol"), nullable=False
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    sku_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("skus.id", name="fk_dol_sku"), nullable=False
    )
    uom_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("uoms.id", name="fk_dol_uom"), nullable=False
    )
    qty_shipped: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    batch_no: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    serial_no: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.current_timestamp()
    )

    delivery_order: Mapped["DeliveryOrder"] = relationship("DeliveryOrder", back_populates="lines")
    sales_order_line: Mapped["SalesOrderLine"] = relationship(
        "SalesOrderLine", back_populates="delivery_lines"
    )
    sku: Mapped["SKU"] = relationship("SKU")
    uom: Mapped["UOM"] = relationship("UOM")
