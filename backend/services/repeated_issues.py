"""Repeated issue detection — finds clusters of similar tickets.

Scans recent tickets, groups by embedding similarity, and flags
patterns where 3+ similar tickets appear within a time window.
Helps identify root causes that keep generating tickets.
"""

import logging
from datetime import datetime, timedelta, timezone

import numpy as np

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.80  # cosine similarity to be "same issue"
MIN_CLUSTER_SIZE = 3         # minimum tickets to flag as repeated
LOOKBACK_DAYS = 7            # scan window


def _cosine_sim(a, b):
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    dot = np.dot(va, vb)
    norm = np.linalg.norm(va) * np.linalg.norm(vb)
    return float(dot / norm) if norm > 0 else 0.0


def detect_repeated_issues(db, lookback_days: int = LOOKBACK_DAYS,
                           min_cluster: int = MIN_CLUSTER_SIZE,
                           threshold: float = SIMILARITY_THRESHOLD) -> list[dict]:
    """Scan recent tickets and detect clusters of similar issues.

    Uses greedy clustering: pick unassigned ticket, find all similar
    unassigned tickets (cosine > threshold), form a cluster. Repeat.
    """
    since = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()

    cursor = db.aql.execute(
        """FOR t IN tickets
            FILTER t.created_at >= @since AND t.embedding != null
            RETURN {
                id: t._key, title: t.title, category: t.category,
                embedding: t.embedding, created_at: t.created_at,
                routed_to: t.routed_to, status: t.status
            }""",
        bind_vars={"since": since},
    )
    tickets = list(cursor)

    if len(tickets) < min_cluster:
        return []

    # Greedy clustering
    assigned = set()
    clusters = []

    for i, ticket in enumerate(tickets):
        if ticket["id"] in assigned:
            continue

        cluster_tickets = [ticket]
        assigned.add(ticket["id"])

        for j in range(i + 1, len(tickets)):
            other = tickets[j]
            if other["id"] in assigned:
                continue
            sim = _cosine_sim(ticket["embedding"], other["embedding"])
            if sim >= threshold:
                cluster_tickets.append(other)
                assigned.add(other["id"])

        if len(cluster_tickets) >= min_cluster:
            # Compute cluster center embedding
            embeddings = [t["embedding"] for t in cluster_tickets]
            center = np.mean(embeddings, axis=0).tolist()

            # Most common category in cluster
            categories = [t["category"] for t in cluster_tickets if t.get("category")]
            top_category = max(set(categories), key=categories.count) if categories else None

            clusters.append({
                "ticket_ids": [t["id"] for t in cluster_tickets],
                "ticket_titles": [t["title"] for t in cluster_tickets],
                "count": len(cluster_tickets),
                "category": top_category,
                "representative_title": cluster_tickets[0]["title"],
                "center_embedding": center,
                "first_seen": min(t["created_at"] for t in cluster_tickets),
                "last_seen": max(t["created_at"] for t in cluster_tickets),
            })

    clusters.sort(key=lambda c: c["count"], reverse=True)
    return clusters


def save_repeated_issues(db, clusters: list[dict]) -> int:
    """Save detected clusters to repeated_issues collection. Replaces previous results."""
    col = db.collection("repeated_issues")
    col.truncate()

    now = datetime.now(timezone.utc).isoformat()
    saved = 0

    for i, cluster in enumerate(clusters):
        col.insert({
            "_key": f"cluster-{i+1}",
            "ticket_ids": cluster["ticket_ids"],
            "ticket_titles": cluster["ticket_titles"],
            "count": cluster["count"],
            "category": cluster["category"],
            "representative_title": cluster["representative_title"],
            "center_embedding": cluster["center_embedding"],
            "first_seen": cluster["first_seen"],
            "last_seen": cluster["last_seen"],
            "detected_at": now,
        })
        saved += 1

    logger.info("Saved %d repeated issue clusters", saved)
    return saved


def check_repeated_match(db, embedding: list[float], threshold: float = SIMILARITY_THRESHOLD) -> dict | None:
    """Check if a new ticket matches a known repeated issue pattern."""
    try:
        cursor = db.aql.execute("FOR ri IN repeated_issues RETURN ri")
        for ri in cursor:
            if ri.get("center_embedding"):
                sim = _cosine_sim(embedding, ri["center_embedding"])
                if sim >= threshold:
                    return {
                        "cluster_id": ri["_key"],
                        "representative_title": ri.get("representative_title"),
                        "count": ri.get("count"),
                        "category": ri.get("category"),
                        "similarity": round(sim, 3),
                    }
    except Exception as exc:
        logger.warning("Repeated issue check failed: %s", exc)
    return None
