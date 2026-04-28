"""
Integration tests for /api/ai/ocr/purchase-order — exercises the full SSE
pipeline (gate → quota → storage → service → stream) with anthropic + DB
mocked.

These tests use FastAPI dependency overrides so we don't need a live MySQL or
Redis. They focus on what only the router can express: HTTP status codes,
SSE event ordering, and error payload shape.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.enums import AIFeature, FileCategory
from app.main import app
from app.schemas.ai import OCRPurchaseOrder


def _mock_session() -> AsyncMock:
    session = AsyncMock()
    session.info = {}
    session.add = MagicMock()
    return session


def _mock_user(user_id: int = 1, org_id: int = 1) -> MagicMock:
    u = MagicMock()
    u.id = user_id
    u.organization_id = org_id
    return u


def _mock_uploaded(file_id: int = 100, mime: str = "image/jpeg") -> MagicMock:
    f = MagicMock()
    f.id = file_id
    f.mime_type = mime
    f.stored_path = f"/tmp/{file_id}.jpg"
    return f


def _reset_sse_app_status() -> None:
    """sse-starlette caches a module-level asyncio.Event; reset between tests
    so each TestClient gets a fresh event bound to its own loop."""
    import sse_starlette.sse as sse_mod
    sse_mod.AppStatus.should_exit_event = None
    sse_mod.AppStatus.should_exit = False


@pytest.fixture
def client() -> TestClient:
    """TestClient with auth + DB overridden, gate forced enabled, quota stubbed."""
    _reset_sse_app_status()
    session = _mock_session()
    user = _mock_user()

    async def _override_db():
        yield session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: user

    with patch("app.routers.ai.AIFeatureGate") as gate, \
         patch("app.routers.ai.check_and_increment", new=AsyncMock(return_value=1)), \
         patch("app.routers.ai.storage") as mock_storage:
        gate.is_enabled = AsyncMock(return_value=True)
        mock_storage.save_upload = AsyncMock(return_value=_mock_uploaded())
        with TestClient(app) as c:
            c._session = session  # type: ignore[attr-defined]
            yield c

    app.dependency_overrides.clear()


def _parse_sse(body: str) -> list[dict]:
    """Split a text/event-stream body into a list of {event, data} dicts."""
    events: list[dict] = []
    current: dict[str, str] = {}
    for line in body.splitlines():
        if line == "":
            if current:
                events.append(current)
                current = {}
            continue
        if line.startswith(":"):  # comment / keepalive
            continue
        key, _, value = line.partition(":")
        value = value.lstrip()
        current[key] = value
    if current:
        events.append(current)
    return events


_OCR_SAMPLE = OCRPurchaseOrder(
    supplier_name="Tan Chong Trading Sdn Bhd",
    supplier_tin="C12345678901",
    currency="MYR",
    lines=[],
    confidence="high",
)


class TestOCRRouterFlow:
    def test_gate_disabled_returns_422(self) -> None:
        async def _override_db():
            yield _mock_session()

        app.dependency_overrides[get_db] = _override_db
        app.dependency_overrides[get_current_user] = lambda: _mock_user()
        try:
            with patch("app.routers.ai.AIFeatureGate") as gate:
                gate.is_enabled = AsyncMock(return_value=False)
                with TestClient(app) as c:
                    res = c.post(
                        "/api/ai/ocr/purchase-order",
                        files={"file": ("invoice.jpg", b"x" * 100, "image/jpeg")},
                    )
            assert res.status_code == 422
            body = res.json()
            assert body["error_code"] == "AI_FEATURE_DISABLED"
        finally:
            app.dependency_overrides.clear()

    def test_unauthenticated_returns_401(self) -> None:
        # No dependency override → real auth runs and rejects.
        with TestClient(app) as c:
            res = c.post(
                "/api/ai/ocr/purchase-order",
                files={"file": ("invoice.jpg", b"x", "image/jpeg")},
            )
        assert res.status_code == 401

    def test_happy_path_streams_progress_and_done(self, client: TestClient) -> None:
        with patch("app.routers.ai.ocr_service") as svc:
            svc.extract_purchase_order = AsyncMock(return_value=_OCR_SAMPLE)
            res = client.post(
                "/api/ai/ocr/purchase-order",
                files={"file": ("invoice.jpg", b"img-bytes", "image/jpeg")},
            )

        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/event-stream")

        events = _parse_sse(res.text)
        # uploaded → calling_ai → parsing → done
        names = [e.get("event") for e in events]
        assert names == ["progress", "progress", "progress", "done"]

        first = json.loads(events[0]["data"])
        assert first["stage"] == "uploaded"
        assert first["progress"] == 20
        assert first["file_id"] == 100

        last = json.loads(events[-1]["data"])
        assert last["stage"] == "done"
        assert last["progress"] == 100
        assert last["result"]["supplier_name"] == "Tan Chong Trading Sdn Bhd"
        assert last["result"]["currency"] == "MYR"

    def test_ocr_timeout_emits_error_event(self, client: TestClient) -> None:
        import asyncio

        async def _raise_timeout(*_args, **_kwargs):
            raise asyncio.TimeoutError()

        with patch("app.routers.ai.ocr_service") as svc:
            # asyncio.wait_for re-raises whatever the inner coroutine raises if
            # it's not its own TimeoutError, so we raise it directly here to
            # exercise the same handler branch without a real wall-clock wait.
            svc.extract_purchase_order = _raise_timeout
            res = client.post(
                "/api/ai/ocr/purchase-order",
                files={"file": ("invoice.jpg", b"x", "image/jpeg")},
            )

        assert res.status_code == 200
        events = _parse_sse(res.text)
        names = [e.get("event") for e in events]
        assert "error" in names
        err = next(e for e in events if e.get("event") == "error")
        assert json.loads(err["data"])["code"] == "AI_TIMEOUT"

    def test_storage_called_with_ocr_invoice_category(self, client: TestClient) -> None:
        with patch("app.routers.ai.ocr_service") as svc:
            svc.extract_purchase_order = AsyncMock(return_value=_OCR_SAMPLE)
            client.post(
                "/api/ai/ocr/purchase-order",
                files={"file": ("invoice.jpg", b"x", "image/jpeg")},
            )

        # storage.save_upload is the patched AsyncMock from the fixture
        from app.routers import ai as ai_mod
        save_upload = ai_mod.storage.save_upload
        save_upload.assert_called_once()
        kwargs = save_upload.call_args.kwargs
        assert kwargs["category"] == FileCategory.OCR_INVOICE
        assert kwargs["organization_id"] == 1
        assert kwargs["uploaded_by"] == 1
