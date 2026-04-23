from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base  # noqa: F401 — re-export for models to use

__all__ = ["Base", "TimestampedMixin", "SoftDeleteMixin", "OrgScopedMixin", "VersionedMixin"]


class TimestampedMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.current_timestamp(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )


class SoftDeleteMixin:
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False), nullable=True, default=None
    )


class OrgScopedMixin:
    organization_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)


class VersionedMixin:
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
