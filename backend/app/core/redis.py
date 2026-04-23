import redis.asyncio as aioredis
from redis.asyncio import Redis

from app.core.config import settings


def _make_pool(db: int) -> Redis:
    return aioredis.from_url(
        f"{settings.redis_url}/{db}",
        encoding="utf-8",
        decode_responses=True,
        max_connections=20,
    )


# One pool per logical database — import the one you need
redis_default: Redis = _make_pool(settings.REDIS_DB_DEFAULT)   # Celery broker / misc
redis_cache: Redis = _make_pool(settings.REDIS_DB_CACHE)       # dashboard / hot data
redis_auth: Redis = _make_pool(settings.REDIS_DB_AUTH)         # refresh tokens
redis_rate: Redis = _make_pool(settings.REDIS_DB_RATE)         # rate limit counters


async def ping_redis() -> bool:
    try:
        return bool(await redis_default.ping())
    except Exception:
        return False
