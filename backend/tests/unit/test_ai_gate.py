"""Unit tests for ``AIFeatureGate`` (three-layer AI switch)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.enums import AIFeature
from app.services.ai_gate import AIFeatureGate


def _org(*, master: bool = True, features: dict | None = None) -> MagicMock:
    org = MagicMock()
    org.ai_master_enabled = master
    org.ai_features = features
    return org


def _session_with_org(org: MagicMock | None) -> AsyncMock:
    session = AsyncMock()
    session.get = AsyncMock(return_value=org)
    return session


@pytest.mark.asyncio
class TestAIFeatureGate:
    async def test_global_kill_switch_off(self) -> None:
        """Layer 1: settings.AI_ENABLED=False → always disabled."""
        with patch("app.services.ai_gate.settings") as mock_settings:
            mock_settings.AI_ENABLED = False
            session = _session_with_org(_org())
            assert (
                await AIFeatureGate.is_enabled(session, AIFeature.OCR_INVOICE, 1)
            ) is False
            # Layer 1 short-circuits before any DB lookup.
            session.get.assert_not_called()

    async def test_org_master_off(self) -> None:
        """Layer 2: organization.ai_master_enabled=False → disabled."""
        with patch("app.services.ai_gate.settings") as mock_settings:
            mock_settings.AI_ENABLED = True
            session = _session_with_org(_org(master=False))
            assert (
                await AIFeatureGate.is_enabled(session, AIFeature.OCR_INVOICE, 1)
            ) is False

    async def test_per_feature_off(self) -> None:
        """Layer 3: per-feature flag explicitly false → disabled."""
        with patch("app.services.ai_gate.settings") as mock_settings:
            mock_settings.AI_ENABLED = True
            session = _session_with_org(
                _org(features={"OCR_INVOICE": False, "EINVOICE_PRECHECK": True})
            )
            assert (
                await AIFeatureGate.is_enabled(session, AIFeature.OCR_INVOICE, 1)
            ) is False
            # The other feature stays enabled.
            session = _session_with_org(
                _org(features={"OCR_INVOICE": False, "EINVOICE_PRECHECK": True})
            )
            assert (
                await AIFeatureGate.is_enabled(session, AIFeature.EINVOICE_PRECHECK, 1)
            ) is True

    async def test_all_layers_on(self) -> None:
        """All three layers green → enabled."""
        with patch("app.services.ai_gate.settings") as mock_settings:
            mock_settings.AI_ENABLED = True
            session = _session_with_org(
                _org(features={"OCR_INVOICE": True})
            )
            assert (
                await AIFeatureGate.is_enabled(session, AIFeature.OCR_INVOICE, 1)
            ) is True

    async def test_missing_feature_key_defaults_to_enabled(self) -> None:
        """Layer 3 default-on when the feature key is not in ai_features map.

        New AI features should not silently dark-launch for orgs that haven't
        migrated their ai_features JSON.
        """
        with patch("app.services.ai_gate.settings") as mock_settings:
            mock_settings.AI_ENABLED = True
            session = _session_with_org(_org(features={}))
            assert (
                await AIFeatureGate.is_enabled(session, AIFeature.OCR_INVOICE, 1)
            ) is True

    async def test_lowercase_feature_key_alias(self) -> None:
        """Allow lowercase keys in the JSON map for ergonomics."""
        with patch("app.services.ai_gate.settings") as mock_settings:
            mock_settings.AI_ENABLED = True
            session = _session_with_org(_org(features={"ocr_invoice": False}))
            assert (
                await AIFeatureGate.is_enabled(session, AIFeature.OCR_INVOICE, 1)
            ) is False

    async def test_org_not_found_returns_false(self) -> None:
        """Defensive: missing org row → disabled (don't crash on stale FK)."""
        with patch("app.services.ai_gate.settings") as mock_settings:
            mock_settings.AI_ENABLED = True
            session = _session_with_org(None)
            assert (
                await AIFeatureGate.is_enabled(session, AIFeature.OCR_INVOICE, 999)
            ) is False
