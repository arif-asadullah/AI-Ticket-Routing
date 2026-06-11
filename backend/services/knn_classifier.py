"""
KNN Classifier — Classifier 3 (weight: 0.15)

Takes top 5 similar tickets from vector search and votes by their categories.
No AI model needed — pure math on pre-computed similarities.
Accuracy: ~76% alone (35-ticket benchmark).
"""

from collections import Counter


def classify_knn(similar_tickets: list[dict], k: int = 5) -> dict:
    """
    K-Nearest Neighbors voting from similar past tickets.

    Args:
        similar_tickets: list from vector search, each with 'category' and 'similarity'
        k: number of neighbors to consider

    Returns:
        {
            "category": "Database",
            "confidence": 0.80,
            "neighbors": [{"key": "123", "title": "...", "category": "Database", "similarity": 0.95}],
            "vote_counts": {"Database": 4, "Application": 1}
        }
    """
    if not similar_tickets:
        return {"category": None, "confidence": 0.0, "neighbors": [], "vote_counts": {}}

    # Take top K
    top_k = similar_tickets[:k]

    # Weighted vote by similarity score
    weighted_votes = {}
    for ticket in top_k:
        cat = ticket.get("category")
        sim = ticket.get("similarity", 0.5)
        if cat:
            weighted_votes[cat] = weighted_votes.get(cat, 0) + sim

    if not weighted_votes:
        return {"category": None, "confidence": 0.0, "neighbors": top_k, "vote_counts": {}}

    # Winner = highest weighted score
    winner = max(weighted_votes, key=weighted_votes.get)

    # Simple vote counts (unweighted) for transparency
    vote_counts = dict(Counter(t.get("category") for t in top_k if t.get("category")))

    # Confidence = weighted vote share (proportional to actual voting strength)
    winner_score = weighted_votes[winner]
    total_score = sum(weighted_votes.values())
    confidence = winner_score / total_score if total_score > 0 else 0.0

    return {
        "category": winner,
        "confidence": round(confidence, 3),
        "neighbors": [
            {
                "key": t.get("key"),
                "title": t.get("title", "")[:60],
                "category": t.get("category"),
                "similarity": round(t.get("similarity", 0), 3),
            }
            for t in top_k
        ],
        "vote_counts": vote_counts,
    }
