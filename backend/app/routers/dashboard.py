"""Dashboard router — homepage overview + admin AI summary refresh."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_role
from app.enums import RoleCode
from app.models.organization import User
from app.schemas.dashboard import AISummaryEnvelope, DashboardOverviewResponse
from app.services import dashboard as dashboard_service

router = APIRouter()


@router.get("/overview", response_model=DashboardOverviewResponse)
async def get_dashboard_overview(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardOverviewResponse:
    """KPI + AI summary + 4 inline trend series in one call.

    Cached for 5 minutes. The AI summary uses a 30-min lazy refresh — see
    services/dashboard.py for the full caching contract.
    """
    return await dashboard_service.get_overview(
        db, organization_id=user.organization_id
    )


@router.post("/summary/refresh", response_model=AISummaryEnvelope)
async def refresh_dashboard_summary(
    user: User = Depends(require_role(RoleCode.ADMIN, RoleCode.MANAGER)),
    db: AsyncSession = Depends(get_db),
) -> AISummaryEnvelope:
    """Force regeneration of the AI digest (synchronous; respects 8s timeout).

    Restricted to Admin/Manager since it incurs an LLM call. The endpoint
    falls back to the cached body if the regeneration fails.
    """
    return await dashboard_service.refresh_summary_now(
        db, organization_id=user.organization_id, user_id=user.id
    )
