from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean,
    Date,
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

from app.enums import CostingMethod
from app.models.base import Base, SoftDeleteMixin, TimestampedMixin, VersionedMixin

if TYPE_CHECKING:
    from app.models.organization import Organization, User
    from app.models.master import Brand, Category, UOM, TaxRate, MSICCode


class SKU(Base, SoftDeleteMixin, TimestampedMixin, VersionedMixin):
    __tablename__ = "skus"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_skus_org_code"),
        Index("ix_skus_org_active", "organization_id", "is_active", "deleted_at"),
        Index("ix_skus_org_brand", "organization_id", "brand_id"),
        Index("ix_skus_org_category", "organization_id", "category_id"),
        Index("ix_skus_barcode", "barcode"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", name="fk_skus_org"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    barcode: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_zh: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    brand_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("brands.id", name="fk_skus_brand"), nullable=True
    )
    category_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("categories.id", name="fk_skus_category"), nullable=True
    )
    base_uom_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("uoms.id", name="fk_skus_uom"), nullable=False
    )
    tax_rate_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tax_rates.id", name="fk_skus_tax"), nullable=False
    )
    msic_code: Mapped[Optional[str]] = mapped_column(
        String(8), ForeignKey("msic_codes.code", name="fk_skus_msic"), nullable=True
    )
    unit_price_excl_tax: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    unit_price_incl_tax: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    price_tax_inclusive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="MYR")
    costing_method: Mapped[CostingMethod] = mapped_column(
        Enum(CostingMethod, name="costingmethod"),
        nullable=False,
        default=CostingMethod.WEIGHTED_AVERAGE,
    )
    last_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    safety_stock: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    reorder_point: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    reorder_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    track_batch: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    track_expiry: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    track_serial: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    shelf_life_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    weight_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    aliases: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", name="fk_skus_created_by"), nullable=True
    )
    updated_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", name="fk_skus_updated_by"), nullable=True
    )

    organization: Mapped["Organization"] = relationship("Organization")
    brand: Mapped[Optional["Brand"]] = relationship("Brand")
    category: Mapped[Optional["Category"]] = relationship("Category")
    base_uom: Mapped["UOM"] = relationship("UOM", foreign_keys=[base_uom_id])
    tax_rate: Mapped["TaxRate"] = relationship("TaxRate")
    msic_code_obj: Mapped[Optional["MSICCode"]] = relationship("MSICCode", foreign_keys=[msic_code])
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])
    updater: Mapped[Optional["User"]] = relationship("User", foreign_keys=[updated_by])
