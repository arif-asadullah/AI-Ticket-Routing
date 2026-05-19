"""
Majority-Aware Weighted Aggregator — Stage 4 of classification pipeline.

Combines votes from all 4 classifiers using majority-aware voting:
- Phase 0: Edge cases (0 or 1 classifier)
- Phase 1: Unanimous agreement
- Phase 2: Supermajority (3+ agree) with strength check
- Phase 3: Pair beats singles (2/1/1) with strength check
- Phase 4: 2v2 split with boundary override + tiebreaker
- Phase 5: Total disagreement → weighted fallback

Reviewed and hardened with ChatGPT critique. Fixes the PostgreSQL
misclassification bug where LLM+Keyword overrode KNN+Centroid.
"""

import logging

from backend.services.error_scanner import errors_confirm_category

logger = logging.getLogger(__name__)

# Default classifier weights (tuned via eval — ATR-55)
WEIGHTS = {
    "llm": 0.40,
    "knn": 0.15,
    "centroid": 0.30,
    "keyword": 0.15,
}

# Degradation weight redistribution
DEGRADED_WEIGHTS = {
    "no_data": {"llm": 0.80, "keyword": 0.20},
    "no_llm": {"knn": 0.25, "centroid": 0.50, "keyword": 0.25},
    "emergency": {"keyword": 1.0},
}

# Quality-based confidence caps
QUALITY_CAPS = {
    "HIGH": 0.99,
    "MEDIUM": 0.85,
    "LOW": 0.75,
}

# Scenario caps for each selection method
SCENARIO_CAPS = {
    "unanimous_4": 0.95,
    "unanimous_3": 0.88,
    "unanimous_2": 0.75,
    "strong_supermajority": 0.85,
    "weak_supermajority": 0.65,
    "dissenter_override": 0.60,
    "pair_wins": 0.70,
    "pair_fallback": 0.60,
    "boundary_override": 0.65,
    "weighted_2v2": 0.65,
    "avgconf_2v2": 0.60,
    "centroid_tiebreak": 0.60,
    "unresolved_2v2": 0.50,
    "total_disagreement": 0.50,
    "single_classifier": 0.50,
    "no_votes": 0.0,
}

# Known boundary-confusion pairs (where LLM makes domain mistakes)
KNOWN_BOUNDARY_PAIRS = {
    frozenset({"Database", "Infrastructure"}),
}


def aggregate(
    votes: dict,
    quality_score: str = "HIGH",
    error_codes: list[dict] | None = None,
    graph_confirms_category: bool = False,
) -> dict:
    """Combine classifier votes into final decision using majority-aware voting."""

    # Filter active classifiers
    active_votes = {k: v for k, v in votes.items() if v.get("category")}

    if not active_votes:
        return _build_result(
            winner=None, secondary=None, priority="medium",
            confidence=0.0, agreement="0/0", method="no_votes",
            votes=votes, quality_score=quality_score, reasoning="No classifier returned a valid category",
        )

    weights = _get_weights(active_votes)
    total_active = len(active_votes)

    # Compute weighted scores (used for fallbacks and secondary category)
    category_scores = {}
    for clf, vote in active_votes.items():
        cat = vote["category"]
        w = weights.get(clf, 0)
        c = vote.get("confidence", 0.5)
        category_scores[cat] = category_scores.get(cat, 0) + (w * c)

    # Group voters by category
    category_voters = {}
    for clf, vote in active_votes.items():
        cat = vote["category"]
        if cat not in category_voters:
            category_voters[cat] = []
        category_voters[cat].append({
            "name": clf,
            "weight": weights.get(clf, 0),
            "confidence": vote.get("confidence", 0.5),
        })

    # Sort by vote count then by weighted score
    sorted_cats = sorted(
        category_voters.keys(),
        key=lambda c: (len(category_voters[c]), category_scores.get(c, 0)),
        reverse=True,
    )

    top_cat = sorted_cats[0]
    top_count = len(category_voters[top_cat])

    # ── Phase 0: Single classifier ──
    if total_active == 1:
        winner = top_cat
        method = "single_classifier"
        cap = SCENARIO_CAPS["single_classifier"]
        logger.info("Aggregator: %s via %s (1/1)", winner, method)
        conf = _compute_confidence(winner, category_voters, total_active, cap,
                                   error_codes, graph_confirms_category, quality_score)
        return _build_result(
            winner=winner, secondary=None, priority=_get_priority(active_votes),
            confidence=conf, agreement="1/1", method=method,
            votes=votes, quality_score=quality_score, reasoning=_get_reasoning(active_votes),
        )

    # ── Phase 1: Unanimous agreement ──
    if top_count == total_active:
        winner = top_cat
        method = "unanimous"
        cap_key = f"unanimous_{min(total_active, 4)}"
        cap = SCENARIO_CAPS.get(cap_key, 0.75)
        logger.info("Aggregator: %s via %s (%d/%d)", winner, method, top_count, total_active)
        conf = _compute_confidence(winner, category_voters, total_active, cap,
                                   error_codes, graph_confirms_category, quality_score)
        return _build_result(
            winner=winner, secondary=None, priority=_get_priority(active_votes),
            confidence=conf, agreement=f"{top_count}/{total_active}", method=method,
            votes=votes, quality_score=quality_score, reasoning=_get_reasoning(active_votes),
        )

    # ── Phase 2: Supermajority (3+ agree) — conditional on strength ──
    if top_count >= 3:
        majority_voters = category_voters[top_cat]
        majority_avg_conf = sum(v["confidence"] for v in majority_voters) / len(majority_voters)
        majority_score = sum(v["weight"] * v["confidence"] for v in majority_voters)

        # Find the strongest dissenter
        dissenter_score = 0.0
        dissenter_cat = None
        for cat in sorted_cats[1:]:
            for v in category_voters[cat]:
                s = v["weight"] * v["confidence"]
                if s > dissenter_score:
                    dissenter_score = s
                    dissenter_cat = cat

        if majority_avg_conf >= 0.60:
            winner = top_cat
            method = "strong_supermajority"
            cap = SCENARIO_CAPS["strong_supermajority"]
        elif majority_score >= dissenter_score:
            winner = top_cat
            method = "weak_supermajority"
            cap = SCENARIO_CAPS["weak_supermajority"]
        else:
            winner = dissenter_cat or top_cat
            method = "dissenter_override"
            cap = SCENARIO_CAPS["dissenter_override"]

        agreeing = len(category_voters.get(winner, []))
        logger.info("Aggregator: %s via %s (%d/%d, maj_avg=%.2f)", winner, method, agreeing, total_active, majority_avg_conf)
        secondary = _get_secondary(sorted_cats, category_scores, winner)
        conf = _compute_confidence(winner, category_voters, total_active, cap,
                                   error_codes, graph_confirms_category, quality_score)
        return _build_result(
            winner=winner, secondary=secondary, priority=_get_priority(active_votes),
            confidence=conf, agreement=f"{agreeing}/{total_active}", method=method,
            votes=votes, quality_score=quality_score, reasoning=_get_reasoning(active_votes),
        )

    # ── Phase 3: Pair beats singles (2/1/1) — with strength check ──
    second_cat = sorted_cats[1] if len(sorted_cats) > 1 else None
    second_count = len(category_voters.get(second_cat, [])) if second_cat else 0

    if top_count == 2 and second_count < 2:
        pair = category_voters[top_cat]
        pair_avg_conf = sum(v["confidence"] for v in pair) / len(pair)
        pair_score = sum(v["weight"] * v["confidence"] for v in pair)

        # Best single's weighted score
        best_single_score = 0.0
        for cat in sorted_cats[1:]:
            for v in category_voters[cat]:
                s = v["weight"] * v["confidence"]
                if s > best_single_score:
                    best_single_score = s

        if pair_avg_conf >= 0.60 and pair_score >= best_single_score - 0.05:
            winner = top_cat
            method = "pair_wins"
            cap = SCENARIO_CAPS["pair_wins"]
        else:
            winner = max(category_scores, key=category_scores.get)
            method = "pair_fallback"
            cap = SCENARIO_CAPS["pair_fallback"]

        agreeing = len(category_voters.get(winner, []))
        logger.info("Aggregator: %s via %s (%d/%d, pair_avg=%.2f)", winner, method, agreeing, total_active, pair_avg_conf)
        secondary = _get_secondary(sorted_cats, category_scores, winner)
        conf = _compute_confidence(winner, category_voters, total_active, cap,
                                   error_codes, graph_confirms_category, quality_score)
        return _build_result(
            winner=winner, secondary=secondary, priority=_get_priority(active_votes),
            confidence=conf, agreement=f"{agreeing}/{total_active}", method=method,
            votes=votes, quality_score=quality_score, reasoning=_get_reasoning(active_votes),
        )

    # ── Phase 4: 2v2 split — with boundary override ──
    if top_count == 2 and second_count == 2:
        cat_a, cat_b = sorted_cats[0], sorted_cats[1]
        voters_a = category_voters[cat_a]
        voters_b = category_voters[cat_b]
        names_a = {v["name"] for v in voters_a}
        names_b = {v["name"] for v in voters_b}

        # FIRST: Known boundary override (Database vs Infrastructure)
        categories_in_play = frozenset({cat_a, cat_b})
        if categories_in_play in KNOWN_BOUNDARY_PAIRS:
            # Check if Centroid+KNN are on one side
            semantic_side = None
            semantic_cat = None
            for cat, voters in [(cat_a, voters_a), (cat_b, voters_b)]:
                voter_names = {v["name"] for v in voters}
                if "centroid" in voter_names and "knn" in voter_names:
                    semantic_side = voters
                    semantic_cat = cat
                    break

            if semantic_side and semantic_cat:
                avg_semantic = sum(v["confidence"] for v in semantic_side) / len(semantic_side)
                if avg_semantic >= 0.60:
                    winner = semantic_cat
                    method = "boundary_override"
                    cap = SCENARIO_CAPS["boundary_override"]
                    logger.info("Aggregator: %s via %s (Centroid+KNN override, avg=%.2f)", winner, method, avg_semantic)
                    secondary = cat_a if winner == cat_b else cat_b
                    conf = _compute_confidence(winner, category_voters, total_active, cap,
                                               error_codes, graph_confirms_category, quality_score)
                    return _build_result(
                        winner=winner, secondary=secondary, priority=_get_priority(active_votes),
                        confidence=conf, agreement=f"2/{total_active}", method=method,
                        votes=votes, quality_score=quality_score, reasoning=_get_reasoning(active_votes),
                    )

        # Normal 2v2 tiebreak
        winner, method, cap = _tiebreak_2v2(cat_a, voters_a, cat_b, voters_b, category_scores)
        logger.info("Aggregator: %s via %s (2v2 tiebreak)", winner, method)
        secondary = cat_a if winner == cat_b else cat_b
        conf = _compute_confidence(winner, category_voters, total_active, cap,
                                   error_codes, graph_confirms_category, quality_score)
        return _build_result(
            winner=winner, secondary=secondary, priority=_get_priority(active_votes),
            confidence=conf, agreement=f"2/{total_active}", method=method,
            votes=votes, quality_score=quality_score, reasoning=_get_reasoning(active_votes),
        )

    # ── Phase 5: Total disagreement ──
    winner = max(category_scores, key=category_scores.get)
    method = "total_disagreement"
    cap = SCENARIO_CAPS["total_disagreement"]
    logger.info("Aggregator: %s via %s (1/%d)", winner, method, total_active)
    secondary = _get_secondary(sorted_cats, category_scores, winner)
    conf = _compute_confidence(winner, category_voters, total_active, cap,
                               error_codes, graph_confirms_category, quality_score)
    return _build_result(
        winner=winner, secondary=secondary, priority=_get_priority(active_votes),
        confidence=conf, agreement=f"1/{total_active}", method=method,
        votes=votes, quality_score=quality_score, reasoning=_get_reasoning(active_votes),
    )


# ── Helper functions ──

def _tiebreak_2v2(cat_a, voters_a, cat_b, voters_b, category_scores):
    """Resolve a 2v2 split using the tiebreaker protocol."""
    score_a = sum(v["weight"] * v["confidence"] for v in voters_a)
    score_b = sum(v["weight"] * v["confidence"] for v in voters_b)

    # Step 1: Weighted confidence margin
    if score_a - score_b >= 0.10:
        return cat_a, "weighted_2v2", SCENARIO_CAPS["weighted_2v2"]
    if score_b - score_a >= 0.10:
        return cat_b, "weighted_2v2", SCENARIO_CAPS["weighted_2v2"]

    # Step 2: Average confidence margin
    avg_a = sum(v["confidence"] for v in voters_a) / len(voters_a)
    avg_b = sum(v["confidence"] for v in voters_b) / len(voters_b)
    if avg_a - avg_b >= 0.15:
        return cat_a, "avgconf_2v2", SCENARIO_CAPS["avgconf_2v2"]
    if avg_b - avg_a >= 0.15:
        return cat_b, "avgconf_2v2", SCENARIO_CAPS["avgconf_2v2"]

    # Step 3: Centroid tiebreak
    a_has_centroid = any(v["name"] == "centroid" for v in voters_a)
    b_has_centroid = any(v["name"] == "centroid" for v in voters_b)
    if a_has_centroid and not b_has_centroid:
        centroid_conf = next(v["confidence"] for v in voters_a if v["name"] == "centroid")
        if centroid_conf >= 0.65:
            return cat_a, "centroid_tiebreak", SCENARIO_CAPS["centroid_tiebreak"]
    if b_has_centroid and not a_has_centroid:
        centroid_conf = next(v["confidence"] for v in voters_b if v["name"] == "centroid")
        if centroid_conf >= 0.65:
            return cat_b, "centroid_tiebreak", SCENARIO_CAPS["centroid_tiebreak"]

    # Step 4: Weighted score fallback
    if score_a >= score_b:
        return cat_a, "unresolved_2v2", SCENARIO_CAPS["unresolved_2v2"]
    return cat_b, "unresolved_2v2", SCENARIO_CAPS["unresolved_2v2"]


def _compute_confidence(winner, category_voters, total_active, scenario_cap,
                        error_codes, graph_confirms, quality_score):
    """Compute calibrated confidence using supporter avg + vote share + weight share."""
    voters = category_voters.get(winner, [])
    if not voters:
        return 0.0

    # New confidence formula (fixes the ~25% problem for low-weight pairs)
    supporter_avg_conf = sum(v["confidence"] for v in voters) / len(voters)
    vote_share = len(voters) / max(total_active, 1)
    total_weight = sum(v["weight"] for cat_voters in category_voters.values() for v in cat_voters)
    weight_share = sum(v["weight"] for v in voters) / max(total_weight, 0.01)

    base = (0.60 * supporter_avg_conf) + (0.25 * vote_share) + (0.15 * weight_share)

    # Contextual bonuses
    bonus = 0.0
    if error_codes and errors_confirm_category(error_codes, winner):
        bonus += 0.03
    if graph_confirms:
        bonus += 0.02

    # Safety check: if no individual supporter is confident, cap low
    max_supporter_conf = max(v["confidence"] for v in voters)
    if max_supporter_conf < 0.60 and total_active >= 3:
        base = min(base, 0.55)

    # Apply caps
    quality_cap = QUALITY_CAPS.get(quality_score, 0.99)
    final = min(base + bonus, scenario_cap, quality_cap)
    return round(max(final, 0.0), 3)


def _get_secondary(sorted_cats, category_scores, winner):
    """Get secondary category if score > 0.15."""
    for cat in sorted_cats:
        if cat != winner and category_scores.get(cat, 0) > 0.15:
            return cat
    return None


def _get_priority(active_votes):
    """Get priority from LLM if available."""
    if "llm" in active_votes and active_votes["llm"].get("priority"):
        return active_votes["llm"]["priority"]
    return "medium"


def _get_reasoning(active_votes):
    """Get reasoning from LLM if available."""
    if "llm" in active_votes:
        return active_votes["llm"].get("reasoning", "")
    return ""


def _build_result(winner, secondary, priority, confidence, agreement, method,
                  votes, quality_score, reasoning):
    """Build the standard result dict."""
    return {
        "category": winner,
        "secondary_category": secondary,
        "priority": priority,
        "confidence": confidence,
        "agreement": agreement,
        "selection_method": method,
        "classifier_votes": votes,
        "quality_score": quality_score,
        "reasoning": reasoning,
    }


def _get_weights(active_votes: dict) -> dict:
    """Get appropriate weights based on which classifiers are active."""
    active_keys = set(active_votes.keys())

    if active_keys == {"llm", "knn", "centroid", "keyword"}:
        return WEIGHTS
    if "llm" not in active_keys and {"knn", "centroid", "keyword"} <= active_keys:
        return DEGRADED_WEIGHTS["no_llm"]
    if active_keys == {"llm", "keyword"}:
        return DEGRADED_WEIGHTS["no_data"]
    if active_keys == {"keyword"}:
        return DEGRADED_WEIGHTS["emergency"]

    n = len(active_keys)
    return {k: 1.0 / n for k in active_keys}
