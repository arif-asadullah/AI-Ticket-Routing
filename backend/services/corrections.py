"""Corrections service — tracks human overrides for continuous learning.

Records each override as a structured correction, tracks which classifiers
were wrong, exports corrections as training data, and recomputes centroids.
"""

import logging
from datetime import datetime, timezone

import numpy as np

from backend.core.config import settings

logger = logging.getLogger(__name__)


def find_correction_precedent(db, embedding, threshold: float | None = None) -> dict | None:
    """Return the most similar TRUSTED human correction above the threshold, or None.

    Uses exact COSINE_SIMILARITY over the (small) corrections collection rather
    than the approximate vector index, so a near-identical past correction is
    found reliably regardless of corpus size or index state. This is what makes
    self-learning take effect immediately: correct one ticket, and the next
    near-identical ticket inherits the verified category.

    Only the most recent trusted correction per ticket matters (latest wins),
    so contradictory re-overrides resolve cleanly.
    """
    if not embedding:
        return None
    if threshold is None:
        threshold = settings.CORRECTION_PRECEDENT_MIN_SIMILARITY
    try:
        cursor = db.aql.execute(
            """
            FOR c IN corrections
                FILTER c.is_trusted == true AND c.embedding != null
                COLLECT tid = c.ticket_id INTO group
                LET latest = (
                    FOR g IN group SORT g.c.created_at DESC LIMIT 1 RETURN g.c
                )[0]
                LET sim = COSINE_SIMILARITY(latest.embedding, @embedding)
                FILTER sim >= @threshold
                SORT sim DESC, latest.created_at DESC
                LIMIT 1
                RETURN {
                    category: latest.corrected_category,
                    similarity: sim,
                    ticket_id: latest.ticket_id,
                    title: latest.ticket_title,
                    reason: latest.reason,
                    corrected_by: latest.corrected_by,
                }
            """,
            bind_vars={"embedding": embedding, "threshold": threshold},
        )
        rows = list(cursor)
        return rows[0] if rows else None
    except Exception as exc:
        logger.warning("Correction-precedent lookup failed: %s", exc)
        return None


def record_correction(db, ticket_id: str, ticket_doc: dict, new_category: str,
                      new_priority: str | None, corrected_by: str,
                      corrector_role: str, reason: str) -> dict | None:
    """Record a human correction when an override happens.

    Computes which classifiers were wrong/right and stores a structured
    correction document for training data export and analytics.
    """
    old_category = ticket_doc.get("category")
    if old_category == new_category:
        return None  # Not a category correction, skip

    # Compute which classifiers were wrong vs right
    classifier_votes = ticket_doc.get("classifier_votes") or {}
    classifiers_wrong = []
    classifiers_right = []
    for clf_name, vote in classifier_votes.items():
        if vote and vote.get("category"):
            if vote["category"] == new_category:
                classifiers_right.append(clf_name)
            else:
                classifiers_wrong.append(clf_name)

    # Quality gate
    is_trusted = (
        corrector_role in ("admin", "engineer")
        and reason is not None
        and len(reason.strip()) >= 5
    )

    now = datetime.now(timezone.utc).isoformat()

    doc = {
        "ticket_id": ticket_id,
        "ticket_title": ticket_doc.get("title", ""),
        "ticket_description": ticket_doc.get("description", ""),
        "original_category": old_category,
        "corrected_category": new_category,
        "original_priority": ticket_doc.get("priority"),
        "corrected_priority": new_priority,
        "original_confidence": ticket_doc.get("confidence_score"),
        "classifier_votes": {
            name: {"category": v.get("category"), "confidence": v.get("confidence")}
            for name, v in classifier_votes.items() if v
        },
        "classifiers_wrong": classifiers_wrong,
        "classifiers_right": classifiers_right,
        "corrected_by": corrected_by,
        "corrector_role": corrector_role,
        "reason": reason,
        "is_trusted": is_trusted,
        "embedding": ticket_doc.get("embedding"),
        "created_at": now,
    }

    try:
        result = db.collection("corrections").insert(doc)
        logger.info(
            "Correction recorded: ticket=%s, %s → %s, trusted=%s, wrong=%s",
            ticket_id, old_category, new_category, is_trusted, classifiers_wrong,
        )
        return result
    except Exception as exc:
        logger.warning("Failed to insert correction: %s", exc)
        return None


def recompute_centroids(db) -> list[dict]:
    """Recompute category centroids from all tickets (including corrected ones).

    Reads all tickets with embeddings, groups by current category,
    computes mean embedding per category, writes to category_centroids.
    Idempotent: truncates and reinserts.
    """
    query = """
    FOR t IN tickets
        FILTER t.embedding != null AND t.category != null
        COLLECT cat = t.category INTO group
        LET embeddings = group[*].t.embedding
        RETURN { category: cat, embeddings: embeddings, count: LENGTH(embeddings) }
    """
    cursor = db.aql.execute(query)

    col = db.collection("category_centroids")
    col.truncate()

    now = datetime.now(timezone.utc).isoformat()
    results = []

    for row in cursor:
        cat = row["category"]
        embeddings = row["embeddings"]
        if not embeddings:
            continue
        avg = np.mean(embeddings, axis=0).tolist()
        col.insert({
            "_key": cat.lower().replace(" ", "-"),
            "category": cat,
            "embedding": avg,
            "ticket_count": row["count"],
            "last_updated": now,
        })
        results.append({"category": cat, "ticket_count": row["count"]})

    # Invalidate in-memory cache so next classification uses new centroids
    try:
        from backend.services.centroid_classifier import invalidate_cache
        invalidate_cache()
    except Exception as exc:
        logger.warning("Failed to invalidate centroid cache: %s", exc)

    logger.info("Centroids recomputed: %d categories", len(results))
    return results


def get_correction_stats(db) -> dict:
    """Get correction analytics — override rate, classifier errors, common misclassifications."""
    query = """
    LET all_corrections = (FOR c IN corrections RETURN c)
    LET trusted = (FOR c IN all_corrections FILTER c.is_trusted == true RETURN c)
    LET total_user_tickets = LENGTH(FOR t IN tickets FILTER t._source == "user" RETURN 1)

    LET by_original = (
        FOR c IN trusted
            COLLECT cat = c.original_category WITH COUNT INTO cnt
            SORT cnt DESC
            RETURN { category: cat, count: cnt }
    )

    LET by_corrected = (
        FOR c IN trusted
            COLLECT cat = c.corrected_category WITH COUNT INTO cnt
            SORT cnt DESC
            RETURN { category: cat, count: cnt }
    )

    LET classifier_errors = (
        FOR c IN trusted
            FOR clf IN c.classifiers_wrong
                COLLECT classifier = clf WITH COUNT INTO cnt
                SORT cnt DESC
                RETURN { classifier: classifier, wrong_count: cnt }
    )

    LET common_pairs = (
        FOR c IN trusted
            COLLECT from_cat = c.original_category, to_cat = c.corrected_category WITH COUNT INTO cnt
            SORT cnt DESC
            LIMIT 10
            RETURN { from: from_cat, to: to_cat, count: cnt }
    )

    RETURN {
        total_corrections: LENGTH(all_corrections),
        trusted_corrections: LENGTH(trusted),
        override_rate: total_user_tickets > 0
            ? ROUND(LENGTH(trusted) * 1000 / total_user_tickets) / 1000
            : 0,
        by_original_category: by_original,
        by_corrected_category: by_corrected,
        classifier_errors: classifier_errors,
        common_misclassifications: common_pairs
    }
    """
    cursor = db.aql.execute(query)
    return next(cursor, {})
