"""
Weighted Aggregator — Stage 4 of classification pipeline (ATR-134).

Combines votes from all 4 classifiers into a final classification decision.
Applies agreement bonus/penalty, contextual bonuses, confidence calibration,
and quality-based confidence cap.
"""

import logging

from backend.services.error_scanner import errors_confirm_category

logger = logging.getLogger(__name__)

# Default classifier weights
WEIGHTS = {
    "llm": 0.40,
    "knn": 0.30,
    "centroid": 0.20,
    "keyword": 0.10,
}

# Degradation weight redistribution
DEGRADED_WEIGHTS = {
    # Level 3: No graph data (LLM + Keywords only)
    "no_data": {"llm": 0.80, "keyword": 0.20},
    # Level 2: No LLM (KNN + Centroid + Keywords)
    "no_llm": {"knn": 0.45, "centroid": 0.35, "keyword": 0.20},
    # Level 1: Emergency (Keywords only)
    "emergency": {"keyword": 1.0},
}

# Quality-based confidence caps
QUALITY_CAPS = {
    "HIGH": 0.99,
    "MEDIUM": 0.85,
    "LOW": 0.75,
}


def aggregate(
    votes: dict,
    quality_score: str = "HIGH",
    error_codes: list[dict] | None = None,
    graph_confirms_category: bool = False,
) -> dict:
    """
    Combine classifier votes into final decision.

    Args:
        votes: {"llm": {...}, "knn": {...}, "centroid": {...}, "keyword": {...}}
              Each vote has: {"category": str, "confidence": float, ...}
        quality_score: "HIGH", "MEDIUM", or "LOW"
        error_codes: matched error codes from Stage 1
        graph_confirms_category: whether graph context agrees with winning category

    Returns:
        {
            "category": "Database",
            "secondary_category": "Network" or None,
            "priority": "high",
            "confidence": 0.94,
            "agreement": "4/4",
            "classifier_votes": {...},
            "quality_score": "HIGH",
            "reasoning": "..."
        }
    """
    # Filter out classifiers that returned None category
    active_votes = {k: v for k, v in votes.items() if v.get("category")}

    if not active_votes:
        return {
            "category": None,
            "secondary_category": None,
            "priority": "medium",
            "confidence": 0.0,
            "agreement": "0/0",
            "classifier_votes": votes,
            "quality_score": quality_score,
            "reasoning": "No classifier returned a valid category",
        }

    # Determine which weights to use based on available classifiers
    weights = _get_weights(active_votes)

    # Step 1: Weighted category scores
    category_scores = {}
    for classifier, vote in active_votes.items():
        weight = weights.get(classifier, 0)
        cat = vote["category"]
        conf = vote.get("confidence", 0.5)
        category_scores[cat] = category_scores.get(cat, 0) + (weight * conf)

    # Winner
    winner = max(category_scores, key=category_scores.get)

    # Step 2: Agreement bonus/penalty
    total_active = len(active_votes)
    agreeing = sum(1 for v in active_votes.values() if v["category"] == winner)

    if agreeing == total_active and total_active >= 3:
        bonus = 0.05
    elif agreeing >= total_active - 1 and total_active >= 3:
        bonus = 0.00
    elif agreeing >= 2:
        bonus = -0.05
    else:
        bonus = -0.10

    # Step 3: Contextual bonuses
    if error_codes and errors_confirm_category(error_codes, winner):
        bonus += 0.03
    if graph_confirms_category:
        bonus += 0.02

    # Step 4: Raw confidence
    raw = category_scores[winner] + bonus

    # Step 5: Calibration
    if agreeing == total_active and raw >= 0.90:
        calibrated = raw * 0.98
    elif agreeing >= total_active - 1 and raw >= 0.70:
        calibrated = raw * 0.95
    elif agreeing >= 2:
        calibrated = raw * 0.80
    else:
        calibrated = raw * 0.75

    # Step 6: Quality cap
    cap = QUALITY_CAPS.get(quality_score, 0.99)
    final_confidence = min(max(calibrated, 0.0), cap)

    # Step 7: Secondary category
    sorted_cats = sorted(category_scores.items(), key=lambda x: -x[1])
    secondary = None
    if len(sorted_cats) >= 2 and sorted_cats[1][1] > 0.15:
        secondary = sorted_cats[1][0]

    # Priority — take from LLM if available, else majority vote
    priority = "medium"
    if "llm" in active_votes and active_votes["llm"].get("priority"):
        priority = active_votes["llm"]["priority"]

    # Reasoning — take from LLM if available
    reasoning = ""
    if "llm" in active_votes:
        reasoning = active_votes["llm"].get("reasoning", "")

    return {
        "category": winner,
        "secondary_category": secondary,
        "priority": priority,
        "confidence": round(final_confidence, 3),
        "agreement": f"{agreeing}/{total_active}",
        "classifier_votes": votes,
        "quality_score": quality_score,
        "reasoning": reasoning,
    }


def _get_weights(active_votes: dict) -> dict:
    """Get appropriate weights based on which classifiers are active."""
    active_keys = set(active_votes.keys())

    # All 4 active
    if active_keys == {"llm", "knn", "centroid", "keyword"}:
        return WEIGHTS

    # No LLM
    if "llm" not in active_keys and {"knn", "centroid", "keyword"} <= active_keys:
        return DEGRADED_WEIGHTS["no_llm"]

    # LLM + Keywords only (no data)
    if active_keys == {"llm", "keyword"}:
        return DEGRADED_WEIGHTS["no_data"]

    # Keywords only (emergency)
    if active_keys == {"keyword"}:
        return DEGRADED_WEIGHTS["emergency"]

    # Custom — redistribute evenly among active classifiers
    n = len(active_keys)
    return {k: 1.0 / n for k in active_keys}
