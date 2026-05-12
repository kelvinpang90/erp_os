"""Celery task: nightly demo reset at 03:00 Asia/Kuala_Lumpur.

Beat schedule registers this only when ``settings.DEMO_MODE=true``. The same
service function is invoked by the manual Admin button — keep behaviour
parity by going through ``services.demo_reset.run_demo_reset``.
"""

from __future__ import annotations

import asyncio

import structlog

from app.core.config import settings
from app.tasks.db import AsyncSessionLocal
from app.enums import DemoResetStatus, DemoResetTrigger
from app.services.demo_reset import run_demo_reset
from app.tasks.celery_app import celery_app

logger = structlog.get_logger()


async def _run() -> dict[str, str | int]:
    if not settings.DEMO_MODE:
        logger.info("demo_reset_skipped_not_demo")
        return {"status": "skipped", "reason": "DEMO_MODE_OFF"}

    async with AsyncSessionLocal() as session:
        result = await run_demo_reset(
            triggered_by=DemoResetTrigger.SCHEDULED,
            triggered_by_user_id=None,
            session=session,
        )
    logger.info(
        "demo_reset_done",
        status=result.status.value,
        log_id=result.log_id,
        error=result.error_message,
    )
    return {
        "status": result.status.value,
        "log_id": result.log_id,
        "error": result.error_message or "",
    }


@celery_app.task(
    name="app.tasks.demo_reset.task_run_demo_reset_scheduled",
    bind=False,
    ignore_result=True,
)
def task_run_demo_reset_scheduled() -> dict[str, str | int]:
    return asyncio.run(_run())


@celery_app.task(
    name="app.tasks.demo_reset.task_run_demo_reset_manual",
    bind=False,
    ignore_result=True,
)
def task_run_demo_reset_manual(triggered_by_user_id: int) -> dict[str, str | int]:
    """Invoked by ``/api/admin/demo-reset``. Same code path, different trigger."""
    async def _wrap() -> dict[str, str | int]:
        async with AsyncSessionLocal() as session:
            result = await run_demo_reset(
                triggered_by=DemoResetTrigger.MANUAL,
                triggered_by_user_id=triggered_by_user_id,
                session=session,
            )
        return {
            "status": result.status.value,
            "log_id": result.log_id,
            "error": result.error_message or "",
        }

    if not settings.DEMO_MODE:
        # Manual trigger guarded at the router; this is a defence-in-depth check.
        return {"status": DemoResetStatus.FAILURE.value, "log_id": 0, "error": "DEMO_MODE_OFF"}
    return asyncio.run(_wrap())
