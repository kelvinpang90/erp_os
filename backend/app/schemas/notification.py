"""Notification API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.enums import NotificationSeverity, NotificationType


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: NotificationType
    title: str
    body: str | None = None
    i18n_key: str | None = None
    i18n_params: dict[str, Any] | None = None
    target_user_id: int | None = None
    target_role: str | None = None
    related_entity_type: str | None = None
    related_entity_id: int | None = None
    action_url: str | None = None
    severity: NotificationSeverity
    is_read: bool
    read_at: datetime | None = None
    created_at: datetime


class UnreadCountResponse(BaseModel):
    unread: int
