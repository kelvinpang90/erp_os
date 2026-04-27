"""
Shared pytest fixtures for unit, integration, and e2e tests.
"""

from __future__ import annotations

import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-use")
os.environ.setdefault("DATABASE_URL", "mysql+aiomysql://test:test@localhost/test_erp_os")

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


def make_mock_session() -> AsyncMock:
    """Return an AsyncSession mock with sync methods properly stubbed."""
    session = AsyncMock()
    session.info = {}
    session.add = MagicMock()        # sync in SQLAlchemy
    session.delete = MagicMock()     # sync
    # flush / refresh / execute are async — keep as AsyncMock
    return session


@pytest.fixture
def mock_db() -> AsyncMock:
    return make_mock_session()
