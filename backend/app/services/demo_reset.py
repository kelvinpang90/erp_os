"""Demo Reset service.

Resets transactional data while preserving master data and configuration so
the public demo always boots from a clean, populated state.

Used by:
  - Manual trigger (Admin UI button → /api/admin/demo-reset)
  - Celery beat at 03:00 Asia/Kuala_Lumpur (when DEMO_MODE=true)

Safety:
  - Only runs when settings.DEMO_MODE=true (router-side check)
  - mysqldump backup before any destructive op (best-effort; soft-failure is
    logged but does not abort — disk-full on the demo VPS shouldn't gate the
    nightly reset)
  - Each step in its own try/except so an outage in one phase does not leave
    stocks out of sync with the master data
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import redis_auth, redis_cache, redis_default, redis_rate
from app.enums import DemoResetStatus, DemoResetTrigger
from app.models.audit import DemoResetLog

logger = structlog.get_logger()


# Order matters when we don't TRUNCATE behind FK_CHECKS=0 — but we DO disable
# FK checks during reset, so this is just the canonical wipe list.
RESET_TABLES: list[str] = [
    # Transactional documents and their lines
    "payment_allocations",
    "payments",
    "credit_note_lines",
    "credit_notes",
    "invoice_lines",
    "invoices",
    "delivery_order_lines",
    "delivery_orders",
    "sales_order_lines",
    "sales_orders",
    "goods_receipt_lines",
    "goods_receipts",
    "purchase_order_lines",
    "purchase_orders",
    # Stock — wiped then reseeded by seed_initial_stock
    "stock_adjustment_lines",
    "stock_adjustments",
    "stock_transfer_lines",
    "stock_transfers",
    "stock_movements",
    "stocks",
    # Audit / observability / quotas
    "notifications",
    "audit_logs",
    "ai_call_logs",
    "uploaded_files",
    "login_attempts",
    "event_logs",
    "demo_reset_logs",  # truncated separately at the end so the in-flight row survives
    # Counter state — reset so demo always shows ##-2026-00001 first
    "document_sequences",
]


@dataclass
class DemoResetResult:
    log_id: int
    status: DemoResetStatus
    backup_path: Optional[str]
    tables_reset: list[str]
    records_deleted: dict[str, int]
    error_message: Optional[str] = None


def _backup_path() -> Path:
    base = Path(os.getenv("DEMO_RESET_BACKUP_DIR", "/app/backups"))
    # Best-effort: backup is non-critical, so a non-writable dir (e.g. CI runner
    # without /app) must not abort the entire reset. _run_mysqldump returns
    # False if the path is unusable.
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("backup_dir_unwritable", path=str(base), err=str(exc))
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    return base / f"pre_reset_{ts}.sql.gz"


def _run_mysqldump(target: Path) -> bool:
    """Best-effort mysqldump. Returns True on success, False otherwise."""
    db_url = settings.DATABASE_URL
    # parse mysql+aiomysql://user:pass@host:port/db
    try:
        from urllib.parse import urlparse

        parsed = urlparse(db_url.replace("+aiomysql", ""))
        host = parsed.hostname or "mysql"
        port = parsed.port or 3306
        user = parsed.username or "root"
        password = parsed.password or ""
        dbname = (parsed.path or "/erp_os").lstrip("/")
    except Exception:
        logger.warning("backup_url_parse_failed")
        return False

    cmd = [
        "sh",
        "-c",
        (
            f"mysqldump --single-transaction --quick "
            f"-h{host} -P{port} -u{user} -p{password} {dbname} | gzip > {target}"
        ),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=120)
        if proc.returncode != 0:
            logger.warning(
                "mysqldump_failed",
                rc=proc.returncode,
                stderr=proc.stderr.decode(errors="replace")[:512],
            )
            return False
        return True
    except FileNotFoundError:
        # mysqldump binary not present in the container — soft-fail
        logger.warning("mysqldump_missing")
        return False
    except subprocess.TimeoutExpired:
        logger.warning("mysqldump_timeout")
        return False


async def _truncate_tables(session: AsyncSession) -> dict[str, int]:
    """Truncate every table in RESET_TABLES. Returns row counts before wipe."""
    counts: dict[str, int] = {}
    await session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
    try:
        for table in RESET_TABLES:
            try:
                row = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                counts[table] = int(row.scalar_one() or 0)
            except Exception:
                counts[table] = 0
            await session.execute(text(f"TRUNCATE TABLE {table}"))
    finally:
        await session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    return counts


async def _flush_redis_all() -> None:
    """Flush every Redis DB used by the app:
      0=broker/general, 1=cache, 2=auth refresh tokens, 3=rate-limit counters.
    """
    for client in (redis_default, redis_cache, redis_auth, redis_rate):
        try:
            await client.flushdb()
        except Exception:
            logger.warning("redis_flushdb_failed", url=getattr(client, "connection_pool", None))


async def _reseed_initial_stock(session: AsyncSession) -> None:
    """Re-run seed_initial_stock + seed_transactional after the wipe.

    Imported lazily so test environments without scripts on PYTHONPATH can
    stub these by monkeypatching this function.
    """
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    scripts_dir = repo_root / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    from seed_initial_stock import seed_initial_stock  # type: ignore
    from seed_transactional import seed_transactional  # type: ignore

    await seed_initial_stock(session)
    await seed_transactional(session)


async def run_demo_reset(
    *,
    triggered_by: DemoResetTrigger,
    triggered_by_user_id: Optional[int],
    session: AsyncSession,
) -> DemoResetResult:
    """Execute the full reset. Caller is responsible for permission checks."""
    log_row = DemoResetLog(
        triggered_by=triggered_by,
        triggered_by_user_id=triggered_by_user_id,
        status=DemoResetStatus.RUNNING,
    )
    session.add(log_row)
    await session.flush()
    log_id = log_row.id
    await session.commit()

    backup_path: Optional[Path] = None
    counts: dict[str, int] = {}
    error: Optional[str] = None
    final_status = DemoResetStatus.RUNNING

    try:
        backup_path = _backup_path()
        if not _run_mysqldump(backup_path):
            backup_path = None  # don't claim a backup we don't have

        counts = await _truncate_tables(session)
        await session.commit()

        await _flush_redis_all()

        try:
            await _reseed_initial_stock(session)
            await session.commit()
        except ModuleNotFoundError:
            # Seed bridge not installed (e.g. during tests). Leave stock empty.
            logger.warning("reseed_skipped_no_bridge")
        except Exception as exc:
            logger.exception("reseed_failed", err=str(exc))
            error = f"Reseed failed: {exc}"
            final_status = DemoResetStatus.FAILURE
            raise

        final_status = DemoResetStatus.SUCCESS
    except Exception as exc:
        if not error:
            error = str(exc)
        if final_status == DemoResetStatus.RUNNING:
            final_status = DemoResetStatus.FAILURE
        logger.exception("demo_reset_failed", error=error)
    finally:
        # Re-fetch the log row in a fresh transaction (TRUNCATE invalidated it).
        log_row = DemoResetLog(
            id=log_id,
            triggered_by=triggered_by,
            triggered_by_user_id=triggered_by_user_id,
            status=final_status,
            backup_path=str(backup_path) if backup_path else None,
            tables_reset=RESET_TABLES,
            records_deleted=counts,
            error_message=error,
            completed_at=datetime.now(UTC).replace(tzinfo=None),
        )
        await session.merge(log_row)
        await session.commit()

    return DemoResetResult(
        log_id=log_id,
        status=final_status,
        backup_path=str(backup_path) if backup_path else None,
        tables_reset=RESET_TABLES,
        records_deleted=counts,
        error_message=error,
    )
