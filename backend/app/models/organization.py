from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    func,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.enums import WarehouseType
from app.models.base import Base, SoftDeleteMixin, TimestampedMixin

if TYPE_CHECKING:
    from app.models.master import TaxRate, UOM
    from app.models.sku import SKU
    from app.models.partner import Supplier, Customer
    from app.models.purchase import PurchaseOrder, GoodsReceipt
    from app.models.sales import SalesOrder, DeliveryOrder
    from app.models.invoice import Invoice, CreditNote, Payment
    from app.models.stock import Stock, StockMovement, StockTransfer, StockAdjustment
    from app.models.audit import Notification, AuditLog, AICallLog, UploadedFile


class Organization(Base, SoftDeleteMixin, TimestampedMixin):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    registration_no: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    tin: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    sst_registration_no: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    msic_code: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    default_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="MYR")
    address_line1: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    address_line2: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    postcode: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="MY")
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    ai_master_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ai_features: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    settings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    users: Mapped[List["User"]] = relationship("User", back_populates="organization", foreign_keys="User.organization_id")
    roles: Mapped[List["Role"]] = relationship("Role", back_populates="organization")
    warehouses: Mapped[List["Warehouse"]] = relationship("Warehouse", back_populates="organization")


class User(Base, SoftDeleteMixin, TimestampedMixin):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("organization_id", "email", name="uq_users_org_email"),
        Index("ix_users_org_active", "organization_id", "is_active", "deleted_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", name="fk_users_org"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    locale: Mapped[str] = mapped_column(String(8), nullable=False, default="en-US")
    theme: Mapped[str] = mapped_column(String(8), nullable=False, default="light")
    default_warehouse_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("warehouses.id", name="fk_users_default_wh", use_alter=True), nullable=True
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    last_login_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="users", foreign_keys=[organization_id])
    default_warehouse: Mapped[Optional["Warehouse"]] = relationship("Warehouse", foreign_keys=[default_warehouse_id])
    roles: Mapped[List["Role"]] = relationship("Role", secondary="user_roles", back_populates="users")


class Role(Base, TimestampedMixin):
    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_roles_org_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", name="fk_roles_org"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    default_home: Mapped[str] = mapped_column(String(64), nullable=False, default="/app/dashboard")
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="roles")
    users: Mapped[List["User"]] = relationship("User", secondary="user_roles", back_populates="roles")
    permissions: Mapped[List["Permission"]] = relationship("Permission", secondary="role_permissions", back_populates="roles")


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    module: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    roles: Mapped[List["Role"]] = relationship("Role", secondary="role_permissions", back_populates="permissions")


class RolePermission(Base):
    __tablename__ = "role_permissions"
    __table_args__ = (
        Index("ix_role_permissions_perm", "permission_id"),
    )

    role_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("roles.id", name="fk_rp_role", ondelete="CASCADE"), primary_key=True
    )
    permission_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("permissions.id", name="fk_rp_perm", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.current_timestamp()
    )


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (
        Index("ix_user_roles_role", "role_id"),
    )

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", name="fk_ur_user", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("roles.id", name="fk_ur_role", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.current_timestamp()
    )


class Warehouse(Base, SoftDeleteMixin, TimestampedMixin):
    __tablename__ = "warehouses"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_warehouses_org_code"),
        Index("ix_warehouses_org_active", "organization_id", "is_active", "deleted_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", name="fk_warehouses_org"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    type: Mapped[WarehouseType] = mapped_column(
        Enum(WarehouseType, name="warehousetype"), nullable=False, default=WarehouseType.BRANCH
    )
    address_line1: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    address_line2: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    postcode: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="MY")
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    manager_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", name="fk_warehouses_manager"), nullable=True
    )

    organization: Mapped["Organization"] = relationship("Organization", back_populates="warehouses")
    manager: Mapped[Optional["User"]] = relationship("User", foreign_keys=[manager_user_id])
