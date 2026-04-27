"""
Shared pytest fixtures for unit, integration, and e2e tests.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.enums import RoleCode


# ── Shared mock helpers ───────────────────────────────────────────────────────

def make_mock_user(
    user_id: int = 1,
    org_id: int = 1,
    role: RoleCode = RoleCode.ADMIN,
) -> MagicMock:
    user = MagicMock()
    user.id = user_id
    user.organization_id = org_id
    role_obj = MagicMock()
    role_obj.code = role.value
    user.roles = [role_obj]
    return user


@pytest.fixture
def mock_user():
    return make_mock_user()


@pytest.fixture
def mock_db():
    session = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    return session
