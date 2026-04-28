"""
Per-user daily AI quota counters in Redis.

Why a separate counter from slowapi's per-minute limit? slowapi covers burst
abuse. The daily quota covers cost control — e.g. 20 OCR calls/day/user keeps
demo Anthropic spend predictable. Two layers, two scopes.

Key shape:  ``ai:quota:{user_id}:{feature}:{yyyy-mm-dd}`` (UTC date)
TTL:        86400 s (set on first INCR; subsequent INCRs leave TTL alone)

Atomicity: ``INCR`` is atomic; the EXPIRE racing with a parallel INCR is safe
because the worst case is one extra second of TTL — not a correctness issue.
"""

from __future__ import annotations

from datetime import datetime, timezone

import structlog

from app.core.exceptions import RateLimitError
from app.core.redis import redis_rate
from app.enums import AIFeature

log = structlog.get_logger(__name__)

_TTL_SECONDS = 86_400


def _key(user_id: int, feature: AIFeature) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"ai:quota:{user_id}:{feature.value}:{today}"


async def check_and_increment(
    user_id: int,
    feature: AIFeature,
    daily_limit: int,
) -> int:
    """
    Atomically reserve one quota unit for ``user_id`` today.

    Returns the new counter value on success. Raises ``RateLimitError`` when the
    limit would be exceeded; the increment is rolled back so the user does not
    get charged for the rejection.
    """
    key = _key(user_id, feature)
    new_value: int = await redis_rate.incr(key)
    if new_value == 1:
        # First call today — set TTL. fire-and-forget ok; INCR sticks regardless.
        await redis_rate.expire(key, _TTL_SECONDS)

    if new_value > daily_limit:
        # Roll back so a rejected attempt doesn't count toward tomorrow's view.
        await redis_rate.decr(key)
        log.info(
            "ai_quota.exceeded",
            user_id=user_id,
            feature=feature.value,
            daily_limit=daily_limit,
        )
        raise RateLimitError(
            error_code="AI_DAILY_QUOTA_EXCEEDED",
            message=f"Daily {feature.value} quota of {daily_limit} reached. Resets at midnight UTC.",
            detail={"feature": feature.value, "daily_limit": daily_limit},
        )

    return new_value


async def get_usage(user_id: int, feature: AIFeature) -> int:
    """Read-only — returns today's count (0 if no calls yet)."""
    raw = await redis_rate.get(_key(user_id, feature))
    return int(raw) if raw is not None else 0
