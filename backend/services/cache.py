"""Redis connection helper. Fails gracefully if Redis is unavailable."""

import logging

import redis.asyncio as aioredis

from backend.core.config import settings

logger = logging.getLogger(__name__)

_redis: aioredis.Redis | None = None


async def connect_redis() -> aioredis.Redis | None:
    """Connect to Redis and return an async client, or None on failure."""
    global _redis
    try:
        _redis = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )
        await _redis.ping()
        logger.info("Connected to Redis at %s", settings.REDIS_URL)
        return _redis
    except Exception as exc:
        logger.warning("Redis unavailable: %s", exc)
        _redis = None
        return None


async def close_redis() -> None:
    """Close the Redis connection."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        logger.info("Redis connection closed")
    _redis = None
