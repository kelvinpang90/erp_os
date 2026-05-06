"""Admin-only schemas: AI settings, demo reset, event log."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AISettingsResponse(BaseModel):
    master_enabled: bool
    features: dict[str, bool]


class AISettingsUpdate(BaseModel):
    master_enabled: bool
    features: dict[str, bool] = Field(
        default_factory=dict,
        description="Per-feature toggles. Keys: OCR_INVOICE, EINVOICE_PRECHECK, DASHBOARD_SUMMARY",
    )


class DemoResetResponse(BaseModel):
    status: str
    message: str
    demo_reset_log_id: int | None = None


class EventLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    organization_id: int | None
    actor_user_id: int | None
    request_id: str | None
    payload: dict[str, Any] | None
    occurred_at: datetime
