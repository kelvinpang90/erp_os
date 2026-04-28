"""Unit tests for ``OCRService`` — anthropic SDK is mocked end-to-end."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import BusinessRuleError
from app.enums import AICallStatus, AIFeature
from app.services.ocr import OCRService, _calc_cost_usd
from tests.conftest import make_mock_session, make_mock_user


def _patch_log_session():
    """Replace ``app.services.ocr.AsyncSessionLocal`` so the log write doesn't
    hit a real DB. Returns ``(captured_session, patcher_context)`` — use the
    patcher in a ``with`` block, then assert on the session.add calls."""
    log_session = AsyncMock()
    log_session.add = MagicMock()
    log_session.commit = AsyncMock()
    log_session.rollback = AsyncMock()

    @asynccontextmanager
    async def _factory():
        yield log_session

    p = patch("app.services.ocr.AsyncSessionLocal", new=_factory)
    return log_session, p


def _make_uploaded_file(
    *,
    file_id: int = 42,
    mime: str = "image/jpeg",
    stored_path: str = "/tmp/fake.jpg",
) -> MagicMock:
    f = MagicMock()
    f.id = file_id
    f.mime_type = mime
    f.stored_path = stored_path
    return f


def _make_anthropic_response(
    *,
    text: str,
    input_tokens: int = 1200,
    output_tokens: int = 350,
) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    resp.usage = MagicMock()
    resp.usage.input_tokens = input_tokens
    resp.usage.output_tokens = output_tokens
    return resp


_VALID_OCR_JSON = json.dumps(
    {
        "supplier_name": "Tan Chong Trading Sdn Bhd",
        "supplier_tin": "C12345678901",
        "supplier_address": "123 Jalan Maju, KL",
        "invoice_no": "INV-2026-001",
        "business_date": "2026-04-15",
        "currency": "MYR",
        "subtotal_excl_tax": 1000.00,
        "tax_amount": 100.00,
        "total_incl_tax": 1100.00,
        "lines": [
            {
                "description": "Milo 1kg",
                "sku_code": None,
                "qty": 10,
                "uom": "EA",
                "unit_price_excl_tax": 100.00,
                "tax_rate_percent": 10,
                "discount_percent": None,
            }
        ],
        "remarks": None,
        "confidence": "high",
    }
)


@pytest.mark.asyncio
class TestOCRServiceExtract:
    async def test_happy_path_returns_parsed_result(self) -> None:
        client = AsyncMock()
        client.messages.create = AsyncMock(
            return_value=_make_anthropic_response(text=_VALID_OCR_JSON)
        )
        service = OCRService(client=client)

        session = make_mock_session()
        user = make_mock_user()
        uploaded = _make_uploaded_file()
        log_session, log_patch = _patch_log_session()

        with patch("app.services.ocr.storage") as mock_storage, log_patch:
            mock_storage.read_bytes = AsyncMock(return_value=b"fake-image-bytes")
            result = await service.extract_purchase_order(
                uploaded, user=user, session=session
            )

        assert result.supplier_name == "Tan Chong Trading Sdn Bhd"
        assert result.currency == "MYR"
        assert len(result.lines) == 1
        assert result.lines[0].qty == Decimal("10")
        # ai_call_logs row was added to a fresh session and committed
        log_session.add.assert_called_once()
        log_session.commit.assert_awaited_once()
        log_row = log_session.add.call_args.args[0]
        assert log_row.feature == AIFeature.OCR_INVOICE
        assert log_row.status == AICallStatus.SUCCESS
        assert log_row.input_tokens == 1200
        assert log_row.output_tokens == 350
        assert log_row.cost_usd > Decimal("0")

    async def test_invalid_json_raises_and_logs_failure(self) -> None:
        client = AsyncMock()
        client.messages.create = AsyncMock(
            return_value=_make_anthropic_response(text="not json at all")
        )
        service = OCRService(client=client)

        session = make_mock_session()
        user = make_mock_user()
        uploaded = _make_uploaded_file()
        log_session, log_patch = _patch_log_session()

        with patch("app.services.ocr.storage") as mock_storage, log_patch:
            mock_storage.read_bytes = AsyncMock(return_value=b"x")
            with pytest.raises(BusinessRuleError) as ei:
                await service.extract_purchase_order(
                    uploaded, user=user, session=session
                )
        assert ei.value.error_code == "LLM_JSON_PARSE_ERROR"
        # Failure still logged (finally block runs in its own session)
        log_session.add.assert_called_once()
        log_session.commit.assert_awaited_once()
        log_row = log_session.add.call_args.args[0]
        assert log_row.status == AICallStatus.FAILURE
        assert log_row.error_code == "LLM_JSON_PARSE_ERROR"

    async def test_strips_markdown_fences(self) -> None:
        """LLM sometimes wraps JSON in ```json … ``` — we should still parse it."""
        wrapped = f"```json\n{_VALID_OCR_JSON}\n```"
        client = AsyncMock()
        client.messages.create = AsyncMock(
            return_value=_make_anthropic_response(text=wrapped)
        )
        service = OCRService(client=client)

        session = make_mock_session()
        user = make_mock_user()
        uploaded = _make_uploaded_file()
        _, log_patch = _patch_log_session()

        with patch("app.services.ocr.storage") as mock_storage, log_patch:
            mock_storage.read_bytes = AsyncMock(return_value=b"x")
            result = await service.extract_purchase_order(
                uploaded, user=user, session=session
            )
        assert result.supplier_name == "Tan Chong Trading Sdn Bhd"

    async def test_pdf_uses_document_block(self) -> None:
        """PDF MIME → ``type: document``; image MIME → ``type: image``."""
        client = AsyncMock()
        client.messages.create = AsyncMock(
            return_value=_make_anthropic_response(text=_VALID_OCR_JSON)
        )
        service = OCRService(client=client)

        session = make_mock_session()
        user = make_mock_user()
        uploaded = _make_uploaded_file(mime="application/pdf")
        _, log_patch = _patch_log_session()

        with patch("app.services.ocr.storage") as mock_storage, log_patch:
            mock_storage.read_bytes = AsyncMock(return_value=b"x")
            await service.extract_purchase_order(
                uploaded, user=user, session=session
            )

        kwargs = client.messages.create.call_args.kwargs
        content = kwargs["messages"][0]["content"]
        assert content[0]["type"] == "document"
        assert content[0]["source"]["media_type"] == "application/pdf"


class TestCostCalculation:
    def test_sonnet_pricing(self) -> None:
        # Sonnet 4.6: $3 / $15 per Mtok
        # 1M input + 100k output = $3 + $1.5 = $4.5
        cost = _calc_cost_usd("claude-sonnet-4-6", 1_000_000, 100_000)
        assert cost == Decimal("4.500000")

    def test_unknown_model_falls_back_to_default(self) -> None:
        # Default (sonnet pricing) for unknown
        cost = _calc_cost_usd("future-model-x", 1_000_000, 0)
        assert cost == Decimal("3.000000")

    def test_zero_tokens_zero_cost(self) -> None:
        assert _calc_cost_usd("claude-sonnet-4-6", 0, 0) == Decimal("0.000000")
