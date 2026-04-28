"""
Claude Vision based OCR for purchase order invoices.

Flow:
  1. Read the uploaded file from disk (already validated + stored).
  2. Build a base64 ``image`` or ``document`` content block per MIME type.
  3. Call Claude with the OCR system prompt; ask for strict JSON.
  4. Parse the response into ``OCRPurchaseOrder``.
  5. Append an ``ai_call_logs`` row with token + cost + latency.

The router wraps the call in ``asyncio.wait_for`` for hard timeout, and in a
broad ``except`` for graceful fallback ("please fill manually"). The service
itself only raises on programmer error (invalid input).
"""

from __future__ import annotations

import base64
import json
import re
import time
from decimal import Decimal
from typing import Any, Optional

import structlog
from anthropic import AsyncAnthropic
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.exceptions import BusinessRuleError
from app.core.logging import get_request_id
from app.core.storage import storage
from app.enums import AICallStatus, AIFeature
from app.models.audit import AICallLog, UploadedFile
from app.models.organization import User
from app.schemas.ai import OCRPurchaseOrder
from app.services.prompts import load_prompt

log = structlog.get_logger(__name__)


# Pricing per 1M tokens (USD). Updated as of 2026-04. Models we don't know
# fall through to a conservative default to avoid silent under-counting.
_PRICING_USD_PER_MTOK: dict[str, tuple[Decimal, Decimal]] = {
    "claude-sonnet-4-6": (Decimal("3.00"), Decimal("15.00")),
    "claude-opus-4-7":   (Decimal("15.00"), Decimal("75.00")),
    "claude-haiku-4-5-20251001": (Decimal("0.80"), Decimal("4.00")),
}
_DEFAULT_PRICING: tuple[Decimal, Decimal] = (Decimal("3.00"), Decimal("15.00"))


def _calc_cost_usd(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    in_rate, out_rate = _PRICING_USD_PER_MTOK.get(model, _DEFAULT_PRICING)
    cost = (Decimal(input_tokens) * in_rate + Decimal(output_tokens) * out_rate) / Decimal(1_000_000)
    # Numeric(10, 6) on the column → quantize to 6 dp
    return cost.quantize(Decimal("0.000001"))


_JSON_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.MULTILINE)


def _strip_json_fences(text: str) -> str:
    """LLM occasionally wraps JSON in ```json ... ```; tolerate it."""
    return _JSON_FENCE_RE.sub("", text).strip()


class OCRService:
    """Stateless wrapper around the anthropic AsyncAnthropic client."""

    def __init__(self, client: Optional[AsyncAnthropic] = None) -> None:
        self._client = client or AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def extract_purchase_order(
        self,
        uploaded: UploadedFile,
        *,
        user: User,
        session: AsyncSession,  # noqa: ARG002 — kept for symmetry; logging uses its own session
    ) -> OCRPurchaseOrder:
        del session  # explicitly unused — see finally block for why
        prompt = load_prompt("ocr_invoice")
        model = settings.AI_OCR_MODEL or prompt.model

        # Read the file once into memory — invoices are bounded by AI_OCR_MAX_FILE_MB.
        file_bytes = await storage.read_bytes(uploaded.stored_path)

        b64 = base64.b64encode(file_bytes).decode("ascii")
        mime = uploaded.mime_type.lower()
        block_type = "document" if mime == "application/pdf" else "image"
        content_block: dict[str, Any] = {
            "type": block_type,
            "source": {
                "type": "base64",
                "media_type": mime,
                "data": b64,
            },
        }

        started = time.monotonic()
        log_payload: dict[str, Any] = {
            "feature": AIFeature.OCR_INVOICE.value,
            "model": model,
            "uploaded_file_id": uploaded.id,
            "user_id": user.id,
        }
        log.info("ocr.start", **log_payload)

        status = AICallStatus.FAILURE
        error_code: Optional[str] = None
        input_tokens = 0
        output_tokens = 0

        try:
            response = await self._client.messages.create(
                model=model,
                system=prompt.system,
                temperature=prompt.temperature,
                max_tokens=prompt.max_tokens,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            content_block,
                            {"type": "text", "text": prompt.user_template},
                        ],
                    }
                ],
            )
            input_tokens = int(getattr(response.usage, "input_tokens", 0) or 0)
            output_tokens = int(getattr(response.usage, "output_tokens", 0) or 0)

            text_blocks = [b.text for b in response.content if getattr(b, "type", None) == "text"]
            if not text_blocks:
                error_code = "EMPTY_LLM_RESPONSE"
                raise BusinessRuleError(
                    error_code=error_code,
                    message="The model returned no text content.",
                )
            raw = _strip_json_fences("\n".join(text_blocks))

            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as e:
                error_code = "LLM_JSON_PARSE_ERROR"
                log.warning("ocr.json_parse_failed", raw=raw[:500], err=str(e))
                raise BusinessRuleError(
                    error_code=error_code,
                    message="The model response was not valid JSON.",
                ) from e

            try:
                result = OCRPurchaseOrder.model_validate(payload)
            except Exception as e:
                error_code = "LLM_SCHEMA_MISMATCH"
                log.warning("ocr.schema_validation_failed", err=str(e))
                raise BusinessRuleError(
                    error_code=error_code,
                    message="The model response did not match the expected schema.",
                ) from e

            status = AICallStatus.SUCCESS
            return result

        finally:
            latency_ms = int((time.monotonic() - started) * 1000)
            # Use a fresh session for the log row. We can't reuse the request
            # session because, with SSE streaming, FastAPI's get_db dependency
            # commits the request transaction before this generator finishes —
            # so any session.add() here would be silently discarded.
            async with AsyncSessionLocal() as log_session:
                try:
                    log_session.add(
                        AICallLog(
                            organization_id=user.organization_id,
                            user_id=user.id,
                            feature=AIFeature.OCR_INVOICE,
                            provider="anthropic",
                            model=model,
                            endpoint="/api/ai/ocr/purchase-order",
                            prompt_version=prompt.version,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            cost_usd=_calc_cost_usd(model, input_tokens, output_tokens),
                            latency_ms=latency_ms,
                            status=status,
                            error_code=error_code,
                            request_id=get_request_id() or None,
                            metadata_={"uploaded_file_id": uploaded.id},
                        )
                    )
                    await log_session.commit()
                except Exception:  # noqa: BLE001 — never let logging failure mask the OCR result
                    await log_session.rollback()
                    log.exception("ocr.log_persist_failed")
            log.info(
                "ocr.done",
                status=status.value,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                error_code=error_code,
                **log_payload,
            )


# Default singleton — overridden in tests via dependency injection.
ocr_service = OCRService()
