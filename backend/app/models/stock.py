from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    func,
    BigInteger,
    Computed,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.enums import (
    StockAdjustmentReason,
    StockAdjustmentStatus,
    StockMovementSourceType,
    StockMovementType,
    StockTransferStatus,
)
from app.models.base import Base, SoftDeleteMixin, TimestampedMixin, VersionedMixin

if TYPE_CHECKING:
    from app.models.organization import Organization, User, Warehouse
    from app.models.sku import SKU
    from app.models.master import UOM


class Stock(Base, TimestampedMixin, VersionedMixin):
    __tablename__ = "stocks"
    __table_args__ = (
        UniqueConstraint("sku_id", "warehouse_id", name="uq_stocks_sku_warehouse"),
        Index("ix_stocks_org", "organization_id"),
        Index("ix_stocks_warehouse", "warehouse_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", name="fk_stocks_org"), nullable=False
    )
    sku_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("skus.id", name="fk_stocks_sku"), nullable=False
    )
    warehouse_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("warehouses.id", name="fk_stocks_warehouse"), nullable=False
    )
    on_hand: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    reserved: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    quality_hold: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    available: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 4),
        Computed("`on_hand` - `reserved` - `quality_hold`", persisted=False),
        nullable=True,
    )
    incoming: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    in_transit: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    avg_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    last_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    initial_on_hand: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    initial_avg_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    last_movement_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)

    organization: Mapped["Organization"] = relationship("Organization")
    sku: Mapped["SKU"] = relationship("SKU")
    warehouse: Mapped["Warehouse"] = relationship("Warehouse")


class StockMovement(Base):
    __tablename__ = "stock_movements"
    __table_args__ = (
        Index("ix_sm_sku_warehouse", "sku_id", "warehouse_id", "occurred_at"),
        Index("ix_sm_org_type_date", "organization_id", "movement_type", "occurred_at"),
        Index("ix_sm_source", "source_document_type", "source_document_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", name="fk_sm_org"), nullable=False
    )
    sku_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("skus.id", name="fk_sm_sku"), nullable=False
    )
    warehouse_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("warehouses.id", name="fk_sm_warehouse"), nullable=False
    )
    movement_type: Mapped[StockMovementType] = mapped_column(
        Enum(StockMovementType, name="stockmovementtype"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    avg_cost_after: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    source_document_type: Mapped[StockMovementSourceType] = mapped_column(
        Enum(StockMovementSourceType, name="stockmovementsourcetype"), nullable=False
    )
    source_document_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_line_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    batch_no: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    serial_no: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    actor_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", name="fk_sm_actor"), nullable=True
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.current_timestamp()
    )

    organization: Mapped["Organization"] = relationship("Organization")
    sku: Mapped["SKU"] = relationship("SKU")
    warehouse: Mapped["Warehouse"] = relationship("Warehouse")
    actor: Mapped[Optional["User"]] = relationship("User", foreign_keys=[actor_user_id])


class StockTransfer(Base, SoftDeleteMixin, TimestampedMixin, VersionedMixin):
    __tablename__ = "stock_transfers"
    __table_args__ = (
        UniqueConstraint("organization_id", "document_no", name="uq_tr_org_document_no"),
        Index("ix_tr_org_status_date", "organization_id", "status", "business_date"),
        Index("ix_tr_from_wh", "from_warehouse_id"),
        Index("ix_tr_to_wh", "to_warehouse_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", name="fk_tr_org"), nullable=False, index=True
    )
    document_no: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[StockTransferStatus] = mapped_column(
        Enum(StockTransferStatus, name="stocktransferstatus"), nullable=False, default=StockTransferStatus.DRAFT
    )
    from_warehouse_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("warehouses.id", name="fk_tr_from_wh"), nullable=False
    )
    to_warehouse_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("warehouses.id", name="fk_tr_to_wh"), nullable=False
    )
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_arrival_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    actual_arrival_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    remarks: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", name="fk_tr_created_by"), nullable=True
    )
    updated_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", name="fk_tr_updated_by"), nullable=True
    )

    organization: Mapped["Organization"] = relationship("Organization")
    from_warehouse: Mapped["Warehouse"] = relationship("Warehouse", foreign_keys=[from_warehouse_id])
    to_warehouse: Mapped["Warehouse"] = relationship("Warehouse", foreign_keys=[to_warehouse_id])
    lines: Mapped[List["StockTransferLine"]] = relationship(
        "StockTransferLine", back_populates="stock_transfer", cascade="all, delete-orphan"
    )
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])
    updater: Mapped[Optional["User"]] = relationship("User", foreign_keys=[updated_by])


class StockTransferLine(Base):
    __tablename__ = "stock_transfer_lines"
    __table_args__ = (
        UniqueConstraint("stock_transfer_id", "line_no", name="uq_trl_tr_lineno"),
        Index("ix_trl_sku", "sku_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_transfer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("stock_transfers.id", name="fk_trl_tr", ondelete="CASCADE"), nullable=False
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    sku_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("skus.id", name="fk_trl_sku"), nullable=False
    )
    uom_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("uoms.id", name="fk_trl_uom"), nullable=False
    )
    qty_sent: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    qty_received: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    unit_cost_snapshot: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    batch_no: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.current_timestamp()
    )

    stock_transfer: Mapped["StockTransfer"] = relationship("StockTransfer", back_populates="lines")
    sku: Mapped["SKU"] = relationship("SKU")
    uom: Mapped["UOM"] = relationship("UOM")


class StockAdjustment(Base, SoftDeleteMixin, TimestampedMixin, VersionedMixin):
    __tablename__ = "stock_adjustments"
    __table_args__ = (
        UniqueConstraint("organization_id", "document_no", name="uq_adj_org_document_no"),
        Index("ix_adj_org_status_date", "organization_id", "status", "business_date"),
        Index("ix_adj_warehouse", "warehouse_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", name="fk_adj_org"), nullable=False, index=True
    )
    document_no: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[StockAdjustmentStatus] = mapped_column(
        Enum(StockAdjustmentStatus, name="stockadjustmentstatus"),
        nullable=False,
        default=StockAdjustmentStatus.DRAFT,
    )
    warehouse_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("warehouses.id", name="fk_adj_warehouse"), nullable=False
    )
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[StockAdjustmentReason] = mapped_column(
        Enum(StockAdjustmentReason, name="stockadjustmentreason"), nullable=False
    )
    reason_description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    approved_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", name="fk_adj_approved_by"), nullable=True
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    remarks: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", name="fk_adj_created_by"), nullable=True
    )

    organization: Mapped["Organization"] = relationship("Organization")
    warehouse: Mapped["Warehouse"] = relationship("Warehouse")
    approver: Mapped[Optional["User"]] = relationship("User", foreign_keys=[approved_by])
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])
    lines: Mapped[List["StockAdjustmentLine"]] = relationship(
        "StockAdjustmentLine", back_populates="stock_adjustment", cascade="all, delete-orphan"
    )


class StockAdjustmentLine(Base):
    __tablename__ = "stock_adjustment_lines"
    __table_args__ = (
        UniqueConstraint("stock_adjustment_id", "line_no", name="uq_adjl_adj_lineno"),
        Index("ix_adjl_sku", "sku_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_adjustment_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("stock_adjustments.id", name="fk_adjl_adj", ondelete="CASCADE"),
        nullable=False,
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    sku_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("skus.id", name="fk_adjl_sku"), nullable=False
    )
    uom_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("uoms.id", name="fk_adjl_uom"), nullable=False
    )
    qty_before: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    qty_after: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    qty_diff: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 4),
        Computed("`qty_after` - `qty_before`", persisted=False),
        nullable=True,
    )
    unit_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    batch_no: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.current_timestamp()
    )

    stock_adjustment: Mapped["StockAdjustment"] = relationship("StockAdjustment", back_populates="lines")
    sku: Mapped["SKU"] = relationship("SKU")
    uom: Mapped["UOM"] = relationship("UOM")
