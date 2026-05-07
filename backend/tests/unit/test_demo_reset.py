"""Unit tests for W18 demo reset service + Celery task wrappers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.enums import DemoResetStatus, DemoResetTrigger
from app.services import demo_reset as svc


def _make_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.merge = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.rollback = AsyncMock()

    # Each TRUNCATE / SELECT COUNT call goes through session.execute.
    # The COUNT result needs `.scalar_one()` returning an int; for SET FK / TRUNCATE
    # the return value is unused. A MagicMock satisfies both shapes.
    def _exec(*_args, **_kwargs):
        result = MagicMock()
        result.scalar_one.return_value = 0
        return result

    session.execute = AsyncMock(side_effect=_exec)
    return session


@pytest.mark.asyncio
async def test_run_demo_reset_marks_success_when_pipeline_clean() -> None:
    session = _make_session()

    # When session.add is called for the new DemoResetLog, simulate
    # autoincrement id assignment so subsequent code can read .id.
    counter = {"i": 0}

    def _add(obj):
        counter["i"] += 1
        if hasattr(obj, "id") and obj.id is None:
            obj.id = counter["i"]

    session.add.side_effect = _add

    with patch.object(svc, "_run_mysqldump", return_value=True), patch.object(
        svc, "_flush_redis_all", new=AsyncMock(return_value=None)
    ), patch.object(svc, "_reseed_initial_stock", new=AsyncMock(return_value=None)):
        result = await svc.run_demo_reset(
            triggered_by=DemoResetTrigger.MANUAL,
            triggered_by_user_id=42,
            session=session,
        )

    assert result.status == DemoResetStatus.SUCCESS
    assert result.error_message is None
    # Every reset table should have been touched (count + truncate = 2 calls each
    # plus the bracketing SET FOREIGN_KEY_CHECKS pair).
    expected_calls = 2 * len(svc.RESET_TABLES) + 2
    assert session.execute.await_count >= expected_calls


@pytest.mark.asyncio
async def test_run_demo_reset_marks_failure_when_reseed_raises() -> None:
    session = _make_session()
    counter = {"i": 0}

    def _add(obj):
        counter["i"] += 1
        if hasattr(obj, "id") and obj.id is None:
            obj.id = counter["i"]

    session.add.side_effect = _add

    with patch.object(svc, "_run_mysqldump", return_value=True), patch.object(
        svc, "_flush_redis_all", new=AsyncMock(return_value=None)
    ), patch.object(
        svc,
        "_reseed_initial_stock",
        new=AsyncMock(side_effect=RuntimeError("seed boom")),
    ):
        result = await svc.run_demo_reset(
            triggered_by=DemoResetTrigger.SCHEDULED,
            triggered_by_user_id=None,
            session=session,
        )

    assert result.status == DemoResetStatus.FAILURE
    assert result.error_message and "seed boom" in result.error_message


@pytest.mark.asyncio
async def test_run_demo_reset_soft_fails_when_backup_fails() -> None:
    """A failed mysqldump must not abort the reset — the backup is best-effort."""
    session = _make_session()
    counter = {"i": 0}

    def _add(obj):
        counter["i"] += 1
        if hasattr(obj, "id") and obj.id is None:
            obj.id = counter["i"]

    session.add.side_effect = _add

    with patch.object(svc, "_run_mysqldump", return_value=False), patch.object(
        svc, "_flush_redis_all", new=AsyncMock(return_value=None)
    ), patch.object(svc, "_reseed_initial_stock", new=AsyncMock(return_value=None)):
        result = await svc.run_demo_reset(
            triggered_by=DemoResetTrigger.MANUAL,
            triggered_by_user_id=1,
            session=session,
        )

    assert result.status == DemoResetStatus.SUCCESS
    assert result.backup_path is None  # We don't claim a backup we don't have


@pytest.mark.asyncio
async def test_run_demo_reset_skips_reseed_when_bridge_missing() -> None:
    """Tests / minimal envs without seed scripts should still mark SUCCESS."""
    session = _make_session()
    counter = {"i": 0}

    def _add(obj):
        counter["i"] += 1
        if hasattr(obj, "id") and obj.id is None:
            obj.id = counter["i"]

    session.add.side_effect = _add

    with patch.object(svc, "_run_mysqldump", return_value=False), patch.object(
        svc, "_flush_redis_all", new=AsyncMock(return_value=None)
    ), patch.object(
        svc,
        "_reseed_initial_stock",
        new=AsyncMock(side_effect=ModuleNotFoundError("no seed in test env")),
    ):
        result = await svc.run_demo_reset(
            triggered_by=DemoResetTrigger.SCHEDULED,
            triggered_by_user_id=None,
            session=session,
        )

    assert result.status == DemoResetStatus.SUCCESS


def test_celery_manual_task_short_circuits_when_not_demo_mode() -> None:
    from app.tasks import demo_reset as task_mod

    with patch.object(task_mod.settings, "DEMO_MODE", False):
        result = task_mod.task_run_demo_reset_manual(99)

    assert result["status"] == DemoResetStatus.FAILURE.value
    assert result["error"] == "DEMO_MODE_OFF"
