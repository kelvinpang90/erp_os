"""Audit-log read schemas (admin-only viewer)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.enums import AuditAction


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    entity_type: str
    entity_id: int
    action: AuditAction
    actor_user_id: int | None = None
    actor_email: str | None = Field(default=None, description="Joined from users table")
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    ip: str | None = None
    user_agent: str | None = None
    request_id: str | None = None
    occurred_at: datetime
