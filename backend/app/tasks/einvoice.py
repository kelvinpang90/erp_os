"""Celery task: bulk-finalize VALIDATED e-invoices past their 72h window.

Runs every 10 minutes by default (10 seconds in DEMO_MODE) — see
``app.tasks.celery_app`` Beat schedule. Each org gets one ``run_finalize_scan``
call. The scan itself is idempotent so missed cycles do not lose work.
"""

from __future__ import annotations

import asyncio

import structlog
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.organization import Organization
from app.services.einvoice import run_finalize_scan
from app.tasks._helpers import get_system_user_for_org
from app.tasks.celery_app import celery_app

logger = structlog.get_logger()


async def _run() -> dict[str, int]:
    finalized_total = 0
    org_count = 0
    async with AsyncSessionLocal() as session:
        rows = await session.execute(
            select(Organization.id).where(Organization.deleted_at.is_(None))
        )
        org_ids = [r[0] for r in rows.all()]
        for org_id in org_ids:
            user = await get_system_user_for_org(session, org_id)
            if user is None:
                logger.warning("finalize_scan_no_actor", org_id=org_id)
                continue
            try:
                result = await run_finalize_scan(session, org_id=org_id, user=user)
                await session.commit()
                finalized_total += result.finalized_count
                org_count += 1
            except Exception:
                logger.exception("finalize_scan_failed", org_id=org_id)
                await session.rollback()
    logger.info("finalize_scan_done", orgs=org_count, finalized=finalized_total)
    return {"orgs": org_count, "finalized": finalized_total}


@celery_app.task(
    name="app.tasks.einvoice.task_finalize_scan_all_orgs",
    bind=False,
    ignore_result=True,
)
def task_finalize_scan_all_orgs() -> dict[str, int]:
    return asyncio.run(_run())
