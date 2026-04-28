"""
AI router — /api/ai/*

Currently exposes a single SSE endpoint for OCR-based purchase order extraction.
The endpoint chains four stages and pushes a coarse-grained progress event after
each, finishing with either a ``done`` event (carrying the parsed JSON) or an
``error`` event (carrying a code + message) so the frontend can render a
"please fill manually" fallback.

NOTE: Do NOT add ``from __future__ import annotations`` — slowapi resolves
``Body``/``File`` parameters by inspecting concrete types at runtime, and
ForwardRef-only annotations break that.
"""

import asyncio
import json
from typing import AsyncIterator

import structlog
from fastapi import APIRouter, Depends, File, Request, UploadFile
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.core.exceptions import AppException, BusinessRuleError
from app.core.storage import storage
from app.enums import AIFeature, FileCategory
from app.models.organization import User
from app.schemas.ai import OCRPurchaseOrder
from app.services.ai_gate import AIFeatureGate
from app.services.ocr import ocr_service
from app.services.quota import check_and_increment

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
log = structlog.get_logger(__name__)


def _sse(event: str, payload: dict) -> dict:
    """Format a sse-starlette event message."""
    return {"event": event, "data": json.dumps(payload, ensure_ascii=False, default=str)}


@router.post(
    "/ocr/purchase-order",
    summary="Extract PO fields from an uploaded invoice (SSE)",
    response_class=EventSourceResponse,
)
@limiter.limit("5/minute")
async def ocr_purchase_order(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Stream:
      event: progress  data: {"stage":"uploaded","progress":20}
      event: progress  data: {"stage":"calling_ai","progress":40}
      event: progress  data: {"stage":"parsing","progress":80}
      event: done      data: <OCRPurchaseOrder JSON>
      (or)
      event: error     data: {"code":"AI_TIMEOUT","message":"..."}

    Pre-stream gates (any failure returns a normal HTTP error, not an SSE):
      - Auth (Bearer token)
      - Per-IP burst limit (5/min)
      - AI feature gate (env / org master / per-feature)
      - Per-user daily quota (default 20/day)
      - File MIME whitelist + size cap
    """
    # ── Gate 1: AI feature switch ───────────────────────────────────────────
    if not await AIFeatureGate.is_enabled(db, AIFeature.OCR_INVOICE, user.organization_id):
        raise BusinessRuleError(
            error_code="AI_FEATURE_DISABLED",
            message="OCR is currently disabled for your organization.",
        )

    # ── Gate 2: per-user daily quota (raises RateLimitError on exceed) ──────
    await check_and_increment(user.id, AIFeature.OCR_INVOICE, settings.AI_OCR_DAILY_QUOTA)

    # ── Gate 3: persist the upload (validates MIME + size) ──────────────────
    uploaded = await storage.save_upload(
        file,
        category=FileCategory.OCR_INVOICE,
        organization_id=user.organization_id,
        uploaded_by=user.id,
        max_size_mb=settings.AI_OCR_MAX_FILE_MB,
        session=db,
    )

    async def event_gen() -> AsyncIterator[dict]:
        yield _sse("progress", {"stage": "uploaded", "progress": 20, "file_id": uploaded.id})
        yield _sse("progress", {"stage": "calling_ai", "progress": 40})

        try:
            result: OCRPurchaseOrder = await asyncio.wait_for(
                ocr_service.extract_purchase_order(uploaded, user=user, session=db),
                timeout=settings.AI_OCR_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            log.warning("ocr.timeout", uploaded_file_id=uploaded.id, user_id=user.id)
            yield _sse(
                "error",
                {
                    "code": "AI_TIMEOUT",
                    "message": (
                        f"OCR timed out after {settings.AI_OCR_TIMEOUT_SECONDS}s. "
                        "Please fill the form manually."
                    ),
                },
            )
            return
        except AppException as e:
            log.warning("ocr.app_exception", error_code=e.error_code, message=e.message)
            yield _sse("error", {"code": e.error_code, "message": e.message})
            return
        except Exception as e:  # noqa: BLE001 — any unexpected failure should surface as graceful fallback
            log.exception("ocr.unhandled", err=str(e))
            yield _sse(
                "error",
                {"code": "AI_ERROR", "message": "OCR failed. Please fill the form manually."},
            )
            return

        yield _sse("progress", {"stage": "parsing", "progress": 80})
        yield _sse(
            "done",
            {"stage": "done", "progress": 100, "result": json.loads(result.model_dump_json())},
        )

    # X-Accel-Buffering disables nginx buffering for this response specifically.
    return EventSourceResponse(
        event_gen(),
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )
