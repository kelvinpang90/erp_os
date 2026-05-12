"""Celery task: refresh AI dashboard summary for every org every 30 minutes.

Routed to the ``ai`` queue so a long LLM call does not block fast scheduled
work on the ``default`` queue.
"""

from __future__ import annotations

import asyncio

import structlog
from sqlalchemy import select

from app.tasks.db import AsyncSessionLocal
from app.models.organization import Organization
from app.services.dashboard import refresh_summary_now
from app.tasks._helpers import get_system_user_for_org
from app.tasks.celery_app import celery_app

logger = structlog.get_logger()


async def _run() -> dict[str, int]:
    refreshed = 0
    async with AsyncSessionLocal() as session:
        rows = await session.execute(
            select(Organization.id).where(Organization.deleted_at.is_(None))
        )
        org_ids = [r[0] for r in rows.all()]
        for org_id in org_ids:
            user = await get_system_user_for_org(session, org_id)
            user_id = user.id if user else None
            try:
                await refresh_summary_now(
                    session, organization_id=org_id, user_id=user_id
                )
                await session.commit()
                refreshed += 1
            except Exception:
                logger.exception("dashboard_summary_refresh_failed", org_id=org_id)
                await session.rollback()
    logger.info("dashboard_summary_refresh_done", orgs=refreshed)
    return {"orgs_refreshed": refreshed}


@celery_app.task(
    name="app.tasks.dashboard.task_refresh_ai_summary_all_orgs",
    bind=False,
    ignore_result=True,
    queue="ai",
)
def task_refresh_ai_summary_all_orgs() -> dict[str, int]:
    return asyncio.run(_run())
