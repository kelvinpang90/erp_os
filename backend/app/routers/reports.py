"""Reports router — 10 aggregation endpoints for the Reports centre.

All endpoints require Admin or Manager (sales / purchase users see their
own module dashboards, not the cross-cutting reports). Each endpoint takes
an optional ``days`` window and returns a focused Pydantic shape — see
schemas/dashboard.py for the response models.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_role
from app.enums import RoleCode
from app.models.organization import User
from app.schemas.dashboard import (
    AICostMetricsResponse,
    CategoryShareResponse,
    EInvoiceStatusDistributionResponse,
    InventoryTurnoverResponse,
    TopEntityResponse,
    TrendSeriesResponse,
    WarehouseStockDistributionResponse,
)
from app.services import reports as reports_service

router = APIRouter()

_REPORT_ROLES = [RoleCode.ADMIN, RoleCode.MANAGER]


@router.get("/sales-trend", response_model=TrendSeriesResponse)
async def sales_trend(
    days: int = Query(30, ge=1, le=180),
    user: User = Depends(require_role(*_REPORT_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> TrendSeriesResponse:
    return await reports_service.get_sales_trend(
        db, organization_id=user.organization_id, days=days
    )


@router.get("/purchase-trend", response_model=TrendSeriesResponse)
async def purchase_trend(
    days: int = Query(30, ge=1, le=180),
    user: User = Depends(require_role(*_REPORT_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> TrendSeriesResponse:
    return await reports_service.get_purchase_trend(
        db, organization_id=user.organization_id, days=days
    )


@router.get("/top-skus", response_model=TopEntityResponse)
async def top_skus(
    days: int = Query(30, ge=1, le=180),
    limit: int = Query(10, ge=1, le=50),
    user: User = Depends(require_role(*_REPORT_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> TopEntityResponse:
    return await reports_service.get_top_skus_by_sales(
        db, organization_id=user.organization_id, days=days, limit=limit
    )


@router.get("/top-suppliers", response_model=TopEntityResponse)
async def top_suppliers(
    days: int = Query(30, ge=1, le=180),
    limit: int = Query(10, ge=1, le=50),
    user: User = Depends(require_role(*_REPORT_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> TopEntityResponse:
    return await reports_service.get_top_suppliers_by_purchase(
        db, organization_id=user.organization_id, days=days, limit=limit
    )


@router.get("/top-customers", response_model=TopEntityResponse)
async def top_customers(
    days: int = Query(30, ge=1, le=180),
    limit: int = Query(10, ge=1, le=50),
    user: User = Depends(require_role(*_REPORT_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> TopEntityResponse:
    return await reports_service.get_top_customers_by_revenue(
        db, organization_id=user.organization_id, days=days, limit=limit
    )


@router.get("/inventory-turnover", response_model=InventoryTurnoverResponse)
async def inventory_turnover(
    days: int = Query(30, ge=1, le=180),
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(require_role(*_REPORT_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> InventoryTurnoverResponse:
    return await reports_service.get_inventory_turnover(
        db, organization_id=user.organization_id, days=days, limit=limit
    )


@router.get(
    "/warehouse-stock-distribution",
    response_model=WarehouseStockDistributionResponse,
)
async def warehouse_stock_distribution(
    user: User = Depends(require_role(*_REPORT_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> WarehouseStockDistributionResponse:
    return await reports_service.get_warehouse_stock_distribution(
        db, organization_id=user.organization_id
    )


@router.get("/category-sales-share", response_model=CategoryShareResponse)
async def category_sales_share(
    days: int = Query(30, ge=1, le=180),
    user: User = Depends(require_role(*_REPORT_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> CategoryShareResponse:
    return await reports_service.get_category_sales_share(
        db, organization_id=user.organization_id, days=days
    )


@router.get(
    "/einvoice-status-distribution",
    response_model=EInvoiceStatusDistributionResponse,
)
async def einvoice_status_distribution(
    days: int = Query(30, ge=1, le=180),
    user: User = Depends(require_role(*_REPORT_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> EInvoiceStatusDistributionResponse:
    return await reports_service.get_einvoice_status_distribution(
        db, organization_id=user.organization_id, days=days
    )


@router.get("/ai-cost", response_model=AICostMetricsResponse)
async def ai_cost(
    days: int = Query(30, ge=1, le=180),
    user: User = Depends(require_role(*_REPORT_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> AICostMetricsResponse:
    return await reports_service.get_ai_cost_metrics(
        db, organization_id=user.organization_id, days=days
    )
