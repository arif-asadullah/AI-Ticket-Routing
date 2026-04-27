"""
Centroid Classifier — Classifier 3 (weight: 0.20)

Compares ticket embedding to 6 pre-computed category centroids.
Returns closest category. No AI model needed — pure vector math.
Accuracy: ~75% alone.
"""

import logging
import time

import numpy as np

logger = logging.getLogger(__name__)

# Cache centroids in memory
_cached_centroids: list[dict] | None = None
_cache_time: float = 0
CACHE_TTL = 3600  # 1 hour


def _cosine_similarity(a, b):
    """Compute cosine similarity between two vectors."""
    a = np.array(a)
    b = np.array(b)
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def _load_centroids(db) -> list[dict]:
    """Load centroids from ArangoDB (cached)."""
    global _cached_centroids, _cache_time

    now = time.time()
    if _cached_centroids and (now - _cache_time) < CACHE_TTL:
        return _cached_centroids

    try:
        if not db.has_collection("category_centroids"):
            return []

        centroids = []
        for doc in db.collection("category_centroids").all():
            if doc.get("embedding"):
                centroids.append({
                    "category": doc["category"],
                    "embedding": doc["embedding"],
                    "ticket_count": doc.get("ticket_count", 0),
                })

        _cached_centroids = centroids
        _cache_time = now
        logger.info("Centroid cache loaded: %d categories", len(centroids))
        return centroids
    except Exception as exc:
        logger.warning("Failed to load centroids: %s", exc)
        return _cached_centroids or []


def classify_centroid(embedding: list[float], db=None) -> dict:
    """
    Compare ticket embedding to category centroids.

    Returns:
        {
            "category": "Database",
            "confidence": 0.84,
            "distances": {"Database": 0.92, "Infrastructure": 0.65, ...}
        }
    """
    if not embedding:
        return {"category": None, "confidence": 0.0, "distances": {}}

    centroids = _load_centroids(db) if db else (_cached_centroids or [])

    if not centroids:
        return {"category": None, "confidence": 0.0, "distances": {}}

    # Compute similarity to each centroid
    similarities = {}
    for centroid in centroids:
        sim = _cosine_similarity(embedding, centroid["embedding"])
        similarities[centroid["category"]] = round(sim, 4)

    if not similarities:
        return {"category": None, "confidence": 0.0, "distances": {}}

    # Winner = highest similarity (closest centroid)
    winner = max(similarities, key=similarities.get)
    best_sim = similarities[winner]

    # Confidence = normalized: how much closer to winner vs second best
    sorted_sims = sorted(similarities.values(), reverse=True)
    if len(sorted_sims) >= 2:
        gap = sorted_sims[0] - sorted_sims[1]
        # Larger gap = more confident. Gap of 0.1+ = very confident
        confidence = min(0.5 + gap * 5, 0.99)
    else:
        confidence = best_sim

    return {
        "category": winner,
        "confidence": round(confidence, 3),
        "distances": similarities,
    }
