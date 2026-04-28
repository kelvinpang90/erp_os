"""
Three-layer AI feature gate.

Any AI endpoint MUST consult this gate before invoking an LLM. Order:

    1. settings.AI_ENABLED         (env / global kill switch)
    2. organization.ai_master_enabled  (per-org master toggle)
    3. organization.ai_features[<feature>]  (per-feature toggle, JSON map)

Any layer returning False short-circuits the rest. The gate never throws —
callers raise the appropriate domain exception when ``is_enabled`` is False.
"""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.enums import AIFeature
from app.models.organization import Organization

log = structlog.get_logger(__name__)


class AIFeatureGate:
    """Stateless helper — all methods are classmethods so it can be patched in tests."""

    @classmethod
    async def is_enabled(
        cls,
        session: AsyncSession,
        feature: AIFeature,
        organization_id: int,
    ) -> bool:
        if not settings.AI_ENABLED:
            log.debug("ai_gate.disabled.global", feature=feature.value)
            return False

        org = await session.get(Organization, organization_id)
        if org is None:
            log.warning("ai_gate.org_not_found", organization_id=organization_id)
            return False

        if not org.ai_master_enabled:
            log.debug(
                "ai_gate.disabled.org_master",
                feature=feature.value,
                organization_id=organization_id,
            )
            return False

        # Per-feature toggle. Default = True when key missing, so newly added
        # features don't accidentally stay dark for orgs that haven't migrated
        # their settings JSON yet.
        features_map = org.ai_features or {}
        # Accept both the enum value (e.g. "OCR_INVOICE") and a lowercase alias
        # (e.g. "ocr_invoice") for ergonomics in seeded JSON.
        per_feature = features_map.get(feature.value)
        if per_feature is None:
            per_feature = features_map.get(feature.value.lower())
        if per_feature is None:
            per_feature = True

        if not bool(per_feature):
            log.debug(
                "ai_gate.disabled.per_feature",
                feature=feature.value,
                organization_id=organization_id,
            )
            return False

        return True
