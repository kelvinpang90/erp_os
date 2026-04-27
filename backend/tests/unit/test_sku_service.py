"""Unit tests for SKU service — all DB calls mocked."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.enums import CostingMethod
from app.schemas.sku import SKUCreate, SKUUpdate
from app.schemas.common import PaginationParams
from tests.conftest import make_mock_user


def _make_sku(sku_id: int = 1, org_id: int = 1, code: str = "SKU-001") -> MagicMock:
    s = MagicMock()
    s.id = sku_id
    s.organization_id = org_id
    s.code = code
    s.barcode = None
    s.name = "Test SKU"
    s.name_zh = None
    s.description = None
    s.brand_id = None
    s.category_id = None
    s.base_uom_id = 1
    s.tax_rate_id = 1
    s.msic_code = None
    s.unit_price_excl_tax = Decimal("10.00")
    s.unit_price_incl_tax = Decimal("10.60")
    s.price_tax_inclusive = False
    s.currency = "MYR"
    s.costing_method = CostingMethod.WEIGHTED_AVERAGE
    s.last_cost = None
    s.safety_stock = Decimal("0")
    s.reorder_point = Decimal("0")
    s.reorder_qty = Decimal("0")
    s.track_batch = False
    s.track_expiry = False
    s.track_serial = False
    s.shelf_life_days = None
    s.image_url = None
    s.weight_kg = None
    s.is_active = True
    s.deleted_at = None
    s.created_at = datetime(2026, 1, 1)
    s.updated_at = datetime(2026, 1, 1)
    s.brand = None
    s.category = None
    s.base_uom = None
    s.tax_rate = None
    return s


def _make_uom(uom_id: int = 1, org_id: int = 1) -> MagicMock:
    u = MagicMock()
    u.id = uom_id
    u.organization_id = org_id
    return u


def _make_tax_rate(tax_id: int = 1, org_id: int = 1) -> MagicMock:
    t = MagicMock()
    t.id = tax_id
    t.organization_id = org_id
    return t


@pytest.mark.asyncio
async def test_create_sku_success():
    from app.services.sku import create_sku

    mock_db = AsyncMock()
    user = make_mock_user()
    sku = _make_sku()
    uom = _make_uom()
    tax = _make_tax_rate()

    with (
        patch("app.services.sku.SKURepository") as MockSKURepo,
        patch("app.services.sku.UOMRepository") as MockUOMRepo,
        patch("app.services.sku.TaxRateRepository") as MockTaxRepo,
    ):
        sku_repo = MockSKURepo.return_value
        sku_repo.get_by_code = AsyncMock(return_value=None)
        sku_repo.create = AsyncMock(return_value=sku)
        sku_repo.get_detail = AsyncMock(return_value=sku)

        uom_repo = MockUOMRepo.return_value
        uom_repo.get_by_id = AsyncMock(return_value=uom)

        tax_repo = MockTaxRepo.return_value
        tax_repo.get_by_id = AsyncMock(return_value=tax)

        data = SKUCreate(
            code="SKU-001",
            name="Test SKU",
            base_uom_id=1,
            tax_rate_id=1,
        )
        result = await create_sku(mock_db, data, user=user)
        assert result.code == "SKU-001"
        sku_repo.create.assert_called_once()


@pytest.mark.asyncio
async def test_create_sku_duplicate_code():
    from app.services.sku import create_sku

    mock_db = AsyncMock()
    user = make_mock_user()
    existing = _make_sku()

    with patch("app.services.sku.SKURepository") as MockSKURepo:
        sku_repo = MockSKURepo.return_value
        sku_repo.get_by_code = AsyncMock(return_value=existing)

        data = SKUCreate(
            code="SKU-001",
            name="Duplicate",
            base_uom_id=1,
            tax_rate_id=1,
        )
        with pytest.raises(ConflictError):
            await create_sku(mock_db, data, user=user)


@pytest.mark.asyncio
async def test_create_sku_invalid_uom():
    from app.services.sku import create_sku

    mock_db = AsyncMock()
    user = make_mock_user()

    with (
        patch("app.services.sku.SKURepository") as MockSKURepo,
        patch("app.services.sku.UOMRepository") as MockUOMRepo,
    ):
        sku_repo = MockSKURepo.return_value
        sku_repo.get_by_code = AsyncMock(return_value=None)

        uom_repo = MockUOMRepo.return_value
        uom_repo.get_by_id = AsyncMock(return_value=None)  # UOM not found

        data = SKUCreate(
            code="SKU-002",
            name="Test",
            base_uom_id=999,
            tax_rate_id=1,
        )
        with pytest.raises(NotFoundError):
            await create_sku(mock_db, data, user=user)


@pytest.mark.asyncio
async def test_get_sku_not_found():
    from app.services.sku import get_sku

    mock_db = AsyncMock()
    user = make_mock_user()

    with patch("app.services.sku.SKURepository") as MockSKURepo:
        sku_repo = MockSKURepo.return_value
        sku_repo.get_detail = AsyncMock(return_value=None)

        with pytest.raises(NotFoundError):
            await get_sku(mock_db, 999, user=user)


@pytest.mark.asyncio
async def test_delete_sku_soft_deletes():
    from app.services.sku import delete_sku

    mock_db = AsyncMock()
    user = make_mock_user()
    sku = _make_sku()

    with patch("app.services.sku.SKURepository") as MockSKURepo:
        sku_repo = MockSKURepo.return_value
        sku_repo.get_by_id = AsyncMock(return_value=sku)
        sku_repo.soft_delete = AsyncMock(return_value=sku)

        await delete_sku(mock_db, sku.id, user=user)
        sku_repo.soft_delete.assert_called_once_with(sku)


@pytest.mark.asyncio
async def test_list_skus_paginates():
    from app.services.sku import list_skus

    mock_db = AsyncMock()
    user = make_mock_user()
    skus = [_make_sku(i, code=f"SKU-{i:03d}") for i in range(1, 6)]

    with patch("app.services.sku.SKURepository") as MockSKURepo:
        sku_repo = MockSKURepo.return_value
        sku_repo.list_with_filters = AsyncMock(return_value=(skus, 5))

        pagination = PaginationParams(page=1, page_size=20)
        result = await list_skus(mock_db, pagination, user=user)

        assert result.total == 5
        assert len(result.items) == 5
