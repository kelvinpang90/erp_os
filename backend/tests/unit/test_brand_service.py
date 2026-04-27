"""Unit tests for brand service — all DB calls mocked."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.schemas.brand import BrandCreate, BrandUpdate
from app.schemas.common import PaginationParams
from tests.conftest import make_mock_user


def _make_brand(brand_id: int = 1, org_id: int = 1, code: str = "NESTLE") -> MagicMock:
    b = MagicMock()
    b.id = brand_id
    b.organization_id = org_id
    b.code = code
    b.name = "Nestle"
    b.logo_url = None
    b.is_active = True
    b.deleted_at = None
    b.created_at = datetime(2026, 1, 1)
    b.updated_at = datetime(2026, 1, 1)
    return b


@pytest.mark.asyncio
async def test_get_brand_not_found():
    from app.services.brand import get_brand

    mock_db = AsyncMock()
    user = make_mock_user()

    with patch("app.services.brand.BrandRepository") as MockRepo:
        repo = MockRepo.return_value
        repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(NotFoundError):
            await get_brand(mock_db, 999, user=user)


@pytest.mark.asyncio
async def test_get_brand_wrong_org():
    from app.services.brand import get_brand

    mock_db = AsyncMock()
    user = make_mock_user(org_id=1)
    brand = _make_brand(org_id=2)

    with patch("app.services.brand.BrandRepository") as MockRepo:
        repo = MockRepo.return_value
        repo.get_by_id = AsyncMock(return_value=brand)

        with pytest.raises(NotFoundError):
            await get_brand(mock_db, brand.id, user=user)


@pytest.mark.asyncio
async def test_create_brand_success():
    from app.services.brand import create_brand

    mock_db = AsyncMock()
    user = make_mock_user()
    brand = _make_brand()

    with patch("app.services.brand.BrandRepository") as MockRepo:
        repo = MockRepo.return_value
        repo.get_by_code = AsyncMock(return_value=None)
        repo.create = AsyncMock(return_value=brand)

        data = BrandCreate(code="NESTLE", name="Nestle")
        result = await create_brand(mock_db, data, user=user)

        assert result.code == "NESTLE"
        repo.create.assert_called_once()


@pytest.mark.asyncio
async def test_create_brand_duplicate_code():
    from app.services.brand import create_brand

    mock_db = AsyncMock()
    user = make_mock_user()
    existing = _make_brand()

    with patch("app.services.brand.BrandRepository") as MockRepo:
        repo = MockRepo.return_value
        repo.get_by_code = AsyncMock(return_value=existing)

        data = BrandCreate(code="NESTLE", name="Nestle Duplicate")
        with pytest.raises(ConflictError):
            await create_brand(mock_db, data, user=user)


@pytest.mark.asyncio
async def test_update_brand_code_conflict():
    from app.services.brand import update_brand

    mock_db = AsyncMock()
    user = make_mock_user()
    brand = _make_brand(code="OLD")
    conflict = _make_brand(brand_id=2, code="NEW")

    with patch("app.services.brand.BrandRepository") as MockRepo:
        repo = MockRepo.return_value
        repo.get_by_id = AsyncMock(return_value=brand)
        repo.get_by_code = AsyncMock(return_value=conflict)

        with pytest.raises(ConflictError):
            await update_brand(mock_db, 1, BrandUpdate(code="NEW"), user=user)


@pytest.mark.asyncio
async def test_delete_brand_soft_deletes():
    from app.services.brand import delete_brand

    mock_db = AsyncMock()
    user = make_mock_user()
    brand = _make_brand()

    with patch("app.services.brand.BrandRepository") as MockRepo:
        repo = MockRepo.return_value
        repo.get_by_id = AsyncMock(return_value=brand)
        repo.soft_delete = AsyncMock(return_value=brand)

        await delete_brand(mock_db, brand.id, user=user)
        repo.soft_delete.assert_called_once_with(brand)
