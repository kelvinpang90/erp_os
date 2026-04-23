from datetime import datetime
from decimal import Decimal
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
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.enums import (
    AICallStatus,
    AIFeature,
    AuditAction,
    DemoResetStatus,
    DemoResetTrigger,
    FileCategory,
    NotificationSeverity,
    NotificationType,
)
from app.models.base import Base, SoftDeleteMixin

if TYPE_CHECKING:
    from app.models.organization import Organization, User


class DocumentSequence(Base):
    __tablename__ = "document_sequences"
    __table_args__ = (
        UniqueConstraint("organization_id", "doc_type", "year", name="uq_docseq"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", name="fk_docseq_org"), nullable=False, index=True
    )
    doc_type: Mapped[str] = mapped_column(String(16), nullable=False)
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    current_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.current_timestamp(),
        onupdate=func.current_timestamp()
    )

    organization: Mapped["Organization"] = relationship("Organization")


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notif_user_read", "target_user_id", "is_read", "created_at"),
        Index("ix_notif_role_read", "target_role", "is_read", "created_at"),
        Index("ix_notif_org_type", "organization_id", "type", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", name="fk_notif_org"), nullable=False
    )
    type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="notificationtype"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    i18n_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    i18n_params: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    target_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", name="fk_notif_user"), nullable=True
    )
    target_role: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    related_entity_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    related_entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    action_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    severity: Mapped[NotificationSeverity] = mapped_column(
        Enum(NotificationSeverity, name="notificationseverity"),
        nullable=False,
        default=NotificationSeverity.INFO,
    )
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.current_timestamp()
    )

    organization: Mapped["Organization"] = relationship("Organization")
    target_user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[target_user_id])


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_entity", "entity_type", "entity_id", "occurred_at"),
        Index("ix_audit_org_actor", "organization_id", "actor_user_id", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", name="fk_audit_org"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, name="auditaction"), nullable=False
    )
    actor_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", name="fk_audit_actor"), nullable=True
    )
    before: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    after: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.current_timestamp()
    )

    organization: Mapped["Organization"] = relationship("Organization")
    actor: Mapped[Optional["User"]] = relationship("User", foreign_keys=[actor_user_id])


class AICallLog(Base):
    __tablename__ = "ai_call_logs"
    __table_args__ = (
        Index("ix_ailog_org_feat_date", "organization_id", "feature", "created_at"),
        Index("ix_ailog_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", name="fk_ailog_org"), nullable=False
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", name="fk_ailog_user"), nullable=True
    )
    feature: Mapped[AIFeature] = mapped_column(
        Enum(AIFeature, name="aifeature"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    endpoint: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    input_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[AICallStatus] = mapped_column(
        Enum(AICallStatus, name="aicallstatus"), nullable=False
    )
    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.current_timestamp()
    )

    organization: Mapped["Organization"] = relationship("Organization")
    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id])


class UploadedFile(Base, SoftDeleteMixin):
    __tablename__ = "uploaded_files"
    __table_args__ = (
        Index("ix_files_org_category", "organization_id", "category", "created_at"),
        Index("ix_files_related", "related_entity_type", "related_entity_id"),
        Index("ix_files_expires", "expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", name="fk_files_org"), nullable=False
    )
    category: Mapped[FileCategory] = mapped_column(
        Enum(FileCategory, name="filecategory"), nullable=False
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    related_entity_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    related_entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    uploaded_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", name="fk_files_user"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.current_timestamp()
    )

    organization: Mapped["Organization"] = relationship("Organization")
    uploader: Mapped[Optional["User"]] = relationship("User", foreign_keys=[uploaded_by])


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    __table_args__ = (
        Index("ix_login_email_time", "email", "attempted_at"),
        Index("ix_login_ip_time", "ip", "attempted_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(120), nullable=False)
    ip: Mapped[str] = mapped_column(String(45), nullable=False)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    failure_reason: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.current_timestamp()
    )


class DemoResetLog(Base):
    __tablename__ = "demo_reset_logs"
    __table_args__ = (
        Index("ix_demoreset_status_time", "status", "started_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    triggered_by: Mapped[DemoResetTrigger] = mapped_column(
        Enum(DemoResetTrigger, name="demoresettrigger"), nullable=False
    )
    triggered_by_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", name="fk_demoreset_user"), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.current_timestamp()
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    status: Mapped[DemoResetStatus] = mapped_column(
        Enum(DemoResetStatus, name="demoresetstatus"), nullable=False, default=DemoResetStatus.RUNNING
    )
    backup_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tables_reset: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    records_deleted: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    triggered_by_user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[triggered_by_user_id])
