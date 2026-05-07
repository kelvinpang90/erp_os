"""Celery application factory + Beat schedule.

Three queues:
  - default: small recurring jobs (einvoice finalize scan, demo reset)
  - ai: long-running AI generations (dashboard summary refresh)

Beat schedule:
  - einvoice_finalize_scan       every 10 minutes (10s in DEMO_MODE)
  - dashboard_ai_summary_refresh every 30 minutes
  - demo_reset_nightly           daily at 03:00 Asia/Kuala_Lumpur (only if DEMO_MODE)

DSN/credentials come from app.core.config.settings; this module is safe to
import at any time (Celery is a sync framework — no event loop is started here).
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings


def _build_app() -> Celery:
    app = Celery(
        "erp_os",
        broker=settings.celery_broker,
        backend=settings.celery_backend,
        include=[
            "app.tasks.einvoice",
            "app.tasks.dashboard",
            "app.tasks.demo_reset",
        ],
    )

    finalize_interval = 10 if settings.DEMO_MODE else 600  # seconds

    app.conf.update(
        timezone="Asia/Kuala_Lumpur",
        enable_utc=True,
        task_default_queue="default",
        task_queues={
            "default": {"exchange": "default", "routing_key": "default"},
            "ai": {"exchange": "ai", "routing_key": "ai"},
        },
        task_routes={
            "app.tasks.dashboard.*": {"queue": "ai"},
        },
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        beat_schedule={
            "einvoice-finalize-scan": {
                "task": "app.tasks.einvoice.task_finalize_scan_all_orgs",
                "schedule": float(finalize_interval),
            },
            "dashboard-ai-summary-refresh": {
                "task": "app.tasks.dashboard.task_refresh_ai_summary_all_orgs",
                "schedule": 30.0 * 60,
            },
            **(
                {
                    "demo-reset-nightly": {
                        "task": "app.tasks.demo_reset.task_run_demo_reset_scheduled",
                        "schedule": crontab(hour=3, minute=0),
                    }
                }
                if settings.DEMO_MODE
                else {}
            ),
        },
    )
    return app


celery_app = _build_app()
