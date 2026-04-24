"""
User and /me response schemas.

MeResponse is the payload returned by GET /api/auth/me.
It carries the user profile, flat permission list, and the menu tree
so the frontend can render navigation without hardcoding roles.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Menu tree ─────────────────────────────────────────────────────────────────

class MenuNode(BaseModel):
    """A single navigation node in the sidebar menu tree."""

    key: str = Field(description="Unique route key, e.g. 'purchase.orders'")
    path: str = Field(description="Frontend route path, e.g. '/purchase/orders'")
    icon: str = Field(default="", description="Ant Design icon name")
    label: str = Field(description="i18n key, e.g. 'menu.purchase.orders'")
    children: list["MenuNode"] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


MenuNode.model_rebuild()  # resolve forward ref


# ── User ──────────────────────────────────────────────────────────────────────

class UserResponse(BaseModel):
    """Compact user profile returned in API responses."""

    id: int
    email: str
    full_name: str
    avatar_url: Optional[str] = None
    locale: str
    theme: str
    organization_id: int
    last_login_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── /me ───────────────────────────────────────────────────────────────────────

class MeResponse(BaseModel):
    """
    Full response for GET /api/auth/me.

    - user        : compact profile
    - permissions : flat list of permission codes the user holds
                    (union of all role permissions, de-duplicated)
    - menu        : filtered sidebar tree for this user's roles
    """

    user: UserResponse
    permissions: list[str] = Field(
        description="Permission codes, e.g. ['sku.read', 'po.create', ...]"
    )
    menu: list[MenuNode] = Field(description="Sidebar navigation tree")
