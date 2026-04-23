from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean,
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

from app.enums import CustomerType
from app.models.base import Base, SoftDeleteMixin, TimestampedMixin, VersionedMixin

if TYPE_CHECKING:
    from app.models.organization import Organization, User


class Supplier(Base, SoftDeleteMixin, TimestampedMixin, VersionedMixin):
    __tablename__ = "suppliers"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_suppliers_org_code"),
        Index("ix_suppliers_org_active", "organization_id", "is_active", "deleted_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", name="fk_suppliers_org"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_zh: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    registration_no: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    tin: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    sst_registration_no: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    msic_code: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    contact_person: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    address_line1: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    address_line2: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    postcode: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="MY")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="MYR")
    payment_terms_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    credit_limit: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", name="fk_suppliers_created_by"), nullable=True
    )
    updated_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", name="fk_suppliers_updated_by"), nullable=True
    )

    organization: Mapped["Organization"] = relationship("Organization")
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])
    updater: Mapped[Optional["User"]] = relationship("User", foreign_keys=[updated_by])


class Customer(Base, SoftDeleteMixin, TimestampedMixin, VersionedMixin):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_customers_org_code"),
        Index("ix_customers_org_active", "organization_id", "is_active", "deleted_at"),
        Index("ix_customers_org_type", "organization_id", "customer_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", name="fk_customers_org"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_zh: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    customer_type: Mapped[CustomerType] = mapped_column(
        Enum(CustomerType, name="customertype"), nullable=False, default=CustomerType.B2B
    )
    registration_no: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    tin: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    sst_registration_no: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    msic_code: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    contact_person: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    address_line1: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    address_line2: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    postcode: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="MY")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="MYR")
    payment_terms_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    credit_limit: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", name="fk_customers_created_by"), nullable=True
    )
    updated_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", name="fk_customers_updated_by"), nullable=True
    )

    organization: Mapped["Organization"] = relationship("Organization")
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])
    updater: Mapped[Optional["User"]] = relationship("User", foreign_keys=[updated_by])
