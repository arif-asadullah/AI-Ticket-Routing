"""Redis two-tier classification cache.

Tier A — exact text match:
    SHA-256 of (title + description) → cached ClassificationResult, 1 h TTL.
    Expected hit latency: <5 ms.

Tier B — semantic similarity:
    Stores the last 100 ticket embeddings + results in a Redis hash.
    On Tier-A miss, computes cosine similarity against all stored vectors.
    If max similarity > 0.95, returns the cached result.
    Expected hit latency: <10 ms.
"""

import hashlib
import json
import logging
import time

import numpy as np
import redis.asyncio as aioredis

from backend.core.config import settings

logger = logging.getLogger(__name__)

# ── Redis Connection ──

_redis: aioredis.Redis | None = None

TIER_A_TTL = 3600  # 1 hour
TIER_B_KEY = "cache:tier_b:entries"
TIER_B_MAX = 100
TIER_B_THRESHOLD = 0.95


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


# ── Helpers ──

def _text_hash(title: str, description: str) -> str:
    """SHA-256 hash of title + description."""
    raw = f"{title.strip().lower()}||{description.strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _tier_a_key(text_hash: str) -> str:
    return f"cache:tier_a:{text_hash}"


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Fast cosine similarity using numpy."""
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    dot = np.dot(va, vb)
    norm = np.linalg.norm(va) * np.linalg.norm(vb)
    if norm == 0:
        return 0.0
    return float(dot / norm)


# ── Tier A: Exact Text Match ──

async def tier_a_get(rc: aioredis.Redis, title: str, description: str) -> dict | None:
    """Check Tier A cache. Returns cached result or None."""
    if rc is None:
        return None
    try:
        key = _tier_a_key(_text_hash(title, description))
        raw = await rc.get(key)
        if raw:
            logger.info("Cache Tier-A HIT: %s", key[:40])
            return json.loads(raw)
    except Exception as exc:
        logger.warning("Tier-A get error: %s", exc)
    return None


async def tier_a_set(rc: aioredis.Redis, title: str, description: str, result: dict) -> None:
    """Write to Tier A cache with TTL."""
    if rc is None:
        return
    try:
        key = _tier_a_key(_text_hash(title, description))
        await rc.set(key, json.dumps(result), ex=TIER_A_TTL)
        logger.info("Cache Tier-A SET: %s", key[:40])
    except Exception as exc:
        logger.warning("Tier-A set error: %s", exc)


# ── Tier B: Semantic Similarity ──

async def tier_b_get(rc: aioredis.Redis, embedding: list[float]) -> dict | None:
    """Check Tier B cache. Returns cached result if similarity > threshold."""
    if rc is None:
        return None
    try:
        entries = await rc.hgetall(TIER_B_KEY)
        if not entries:
            return None

        best_sim = 0.0
        best_result = None

        for _entry_key, raw in entries.items():
            entry = json.loads(raw)
            sim = _cosine_similarity(embedding, entry["embedding"])
            if sim > best_sim:
                best_sim = sim
                best_result = entry["result"]

        if best_sim >= TIER_B_THRESHOLD:
            logger.info("Cache Tier-B HIT: similarity=%.4f", best_sim)
            return best_result
        else:
            logger.info("Cache Tier-B MISS: best similarity=%.4f < %.2f", best_sim, TIER_B_THRESHOLD)
    except Exception as exc:
        logger.warning("Tier-B get error: %s", exc)
    return None


async def tier_b_set(rc: aioredis.Redis, embedding: list[float], result: dict) -> None:
    """Write to Tier B cache. Keeps at most TIER_B_MAX entries (evicts oldest)."""
    if rc is None:
        return
    try:
        entry_key = str(int(time.time() * 1000))
        entry = {"embedding": embedding, "result": result}
        await rc.hset(TIER_B_KEY, entry_key, json.dumps(entry))

        # Evict oldest if over limit
        count = await rc.hlen(TIER_B_KEY)
        if count > TIER_B_MAX:
            all_keys = await rc.hkeys(TIER_B_KEY)
            all_keys.sort()  # oldest first (timestamp keys)
            to_remove = all_keys[: count - TIER_B_MAX]
            if to_remove:
                await rc.hdel(TIER_B_KEY, *to_remove)

        logger.info("Cache Tier-B SET (total: %d)", min(count, TIER_B_MAX))
    except Exception as exc:
        logger.warning("Tier-B set error: %s", exc)


# ── Combined Lookup ──

async def cache_get(rc: aioredis.Redis, title: str, description: str, embedding: list[float] | None = None) -> tuple[dict | None, str]:
    """Try Tier A then Tier B. Returns (result, tier) where tier is 'A', 'B', or 'miss'."""
    # Tier A
    result = await tier_a_get(rc, title, description)
    if result is not None:
        return result, "A"

    # Tier B (needs embedding)
    if embedding is not None:
        result = await tier_b_get(rc, embedding)
        if result is not None:
            return result, "B"

    return None, "miss"


async def cache_set(rc: aioredis.Redis, title: str, description: str, embedding: list[float] | None, result: dict) -> None:
    """Write to both tiers."""
    await tier_a_set(rc, title, description, result)
    if embedding is not None:
        await tier_b_set(rc, embedding, result)
