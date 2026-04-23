from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    func,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.enums import TaxType
from app.models.base import Base, OrgScopedMixin, SoftDeleteMixin, TimestampedMixin

if TYPE_CHECKING:
    from app.models.organization import Organization


class Currency(Base):
    __tablename__ = "currencies"

    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    symbol: Mapped[str] = mapped_column(String(8), nullable=False)
    decimal_places: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=2)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.current_timestamp()
    )


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"
    __table_args__ = (
        Index("ix_exchange_rates_lookup", "organization_id", "from_currency", "to_currency", "effective_from"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", name="fk_exchange_rates_org"), nullable=False, index=True
    )
    from_currency: Mapped[str] = mapped_column(
        String(3), ForeignKey("currencies.code", name="fk_exchange_rates_from"), nullable=False
    )
    to_currency: Mapped[str] = mapped_column(
        String(3), ForeignKey("currencies.code", name="fk_exchange_rates_to"), nullable=False
    )
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="MANUAL")
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", name="fk_exchange_rates_creator"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.current_timestamp()
    )

    organization: Mapped["Organization"] = relationship("Organization")
    from_currency_obj: Mapped["Currency"] = relationship("Currency", foreign_keys=[from_currency])
    to_currency_obj: Mapped["Currency"] = relationship("Currency", foreign_keys=[to_currency])


class TaxRate(Base, TimestampedMixin):
    __tablename__ = "tax_rates"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_tax_rates_org_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", name="fk_tax_rates_org"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    tax_type: Mapped[TaxType] = mapped_column(Enum(TaxType, name="taxtype"), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    organization: Mapped["Organization"] = relationship("Organization")


class UOM(Base):
    __tablename__ = "uoms"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_uoms_org_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", name="fk_uoms_org"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    name_zh: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.current_timestamp()
    )

    organization: Mapped["Organization"] = relationship("Organization")


class Brand(Base, SoftDeleteMixin, TimestampedMixin):
    __tablename__ = "brands"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_brands_org_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", name="fk_brands_org"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    logo_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    organization: Mapped["Organization"] = relationship("Organization")


class Category(Base, SoftDeleteMixin, TimestampedMixin):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_categories_org_code"),
        Index("ix_categories_parent", "parent_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", name="fk_categories_org"), nullable=False, index=True
    )
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("categories.id", name="fk_categories_parent"), nullable=True
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    name_zh: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    organization: Mapped["Organization"] = relationship("Organization")
    parent: Mapped[Optional["Category"]] = relationship("Category", remote_side="Category.id", back_populates="children")
    children: Mapped[List["Category"]] = relationship("Category", back_populates="parent")


class MSICCode(Base):
    __tablename__ = "msic_codes"

    code: Mapped[str] = mapped_column(String(8), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
