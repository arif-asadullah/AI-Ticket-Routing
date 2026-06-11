"""Unit tests for the majority-aware weighted aggregator.

These tests lock in two recent fixes:
  1. DETERMINISM — identical votes must always produce the same category AND
     confidence, with alphabetical tiebreak in `_pick_winner`.
  2. WEIGHT RENORMALIZATION — when a classifier drops out, the tuned weights are
     renormalized over the active set (LLM stays dominant) instead of collapsing
     to a uniform 1/N split.

All tests are pure functions: no DB, Redis, Ollama, or network. `error_codes`
is always None so the aggregator never calls into the error scanner.
"""

from backend.services.aggregator import (
    aggregate,
    _pick_winner,
    _get_weights,
    WEIGHTS,
    SCENARIO_CAPS,
    QUALITY_CAPS,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _vote(category, confidence=0.8, priority=None):
    v = {"category": category, "confidence": confidence}
    if priority is not None:
        v["priority"] = priority
    return v


RESULT_KEYS = {
    "category",
    "secondary_category",
    "priority",
    "confidence",
    "agreement",
    "selection_method",
    "classifier_votes",
    "quality_score",
    "reasoning",
}


# ── Behavior 1: Unanimous agreement ────────────────────────────────────────────

def test_unanimous_four_votes_winner_and_cap():
    votes = {
        "llm": _vote("Database", 0.9, priority="high"),
        "knn": _vote("Database", 0.8),
        "centroid": _vote("Database", 0.85),
        "keyword": _vote("Database", 0.7),
    }
    result = aggregate(votes, quality_score="HIGH")

    assert result["category"] == "Database"
    assert result["selection_method"] == "unanimous"
    assert result["agreement"] == "4/4"
    # Confidence respects the unanimous_4 scenario cap and stays in [0, 1].
    assert result["confidence"] <= SCENARIO_CAPS["unanimous_4"]
    assert 0.0 <= result["confidence"] <= 1.0


def test_result_has_all_expected_keys():
    votes = {
        "llm": _vote("Network", 0.9, priority="medium"),
        "knn": _vote("Network", 0.8),
        "centroid": _vote("Network", 0.85),
        "keyword": _vote("Network", 0.7),
    }
    result = aggregate(votes)
    assert set(result.keys()) == RESULT_KEYS


# ── Behavior 2: No votes ───────────────────────────────────────────────────────

def test_no_votes_returns_no_votes_result_without_crashing():
    votes = {
        "llm": {"category": None, "confidence": 0.0},
        "knn": {"category": None},
        "centroid": {},
        "keyword": {"category": "", "confidence": 0.0},
    }
    result = aggregate(votes)

    assert result["category"] is None
    assert result["confidence"] == 0.0
    assert result["agreement"] == "0/0"
    assert result["selection_method"] == "no_votes"


def test_empty_votes_dict_does_not_crash():
    result = aggregate({})
    assert result["category"] is None
    assert result["confidence"] == 0.0
    assert result["selection_method"] == "no_votes"


# ── Behavior 3: Null-safety with mixed votes ───────────────────────────────────

def test_null_category_mixed_with_valid_votes_does_not_crash():
    votes = {
        "llm": _vote("Database", 0.9, priority="high"),
        "knn": {"category": None, "confidence": 0.5},  # null vote, must be ignored
        "centroid": _vote("Database", 0.85),
        "keyword": _vote("Database", 0.7),
    }
    result = aggregate(votes)

    # The three valid Database votes still decide; the null KNN vote is dropped.
    assert result["category"] == "Database"
    assert 0.0 <= result["confidence"] <= 1.0
    # Only 3 active votes — agreement should reflect 3 active classifiers.
    assert result["agreement"].endswith("/3")


def test_missing_confidence_key_uses_default_and_does_not_crash():
    votes = {
        "llm": {"category": "Network", "priority": "low"},  # no confidence key
        "centroid": {"category": "Network"},
        "keyword": {"category": "Network"},
    }
    result = aggregate(votes)
    assert result["category"] == "Network"
    assert 0.0 <= result["confidence"] <= 1.0


# ── Behavior 4: Quality caps ────────────────────────────────────────────────────

def test_low_quality_caps_confidence_below_auto_route_threshold():
    votes = {
        "llm": _vote("Database", 0.95, priority="high"),
        "knn": _vote("Database", 0.95),
        "centroid": _vote("Database", 0.95),
        "keyword": _vote("Database", 0.95),
    }
    result = aggregate(votes, quality_score="LOW")

    # LOW quality must keep confidence at/below the 0.69 auto-route threshold
    # so low-quality tickets are sent for human review, never auto-routed.
    assert result["confidence"] <= QUALITY_CAPS["LOW"]
    assert result["confidence"] <= 0.69
    assert result["quality_score"] == "LOW"


def test_medium_quality_cap_respected():
    votes = {
        "llm": _vote("Database", 0.99, priority="high"),
        "knn": _vote("Database", 0.99),
        "centroid": _vote("Database", 0.99),
        "keyword": _vote("Database", 0.99),
    }
    result = aggregate(votes, quality_score="MEDIUM")
    assert result["confidence"] <= QUALITY_CAPS["MEDIUM"]


# ── Behavior 5: Determinism ─────────────────────────────────────────────────────

def test_aggregate_is_deterministic_across_repeated_calls():
    votes = {
        "llm": _vote("Database", 0.9, priority="high"),
        "knn": _vote("Network", 0.8),
        "centroid": _vote("Database", 0.85),
        "keyword": _vote("Network", 0.7),
    }
    first = aggregate(votes)
    second = aggregate(votes)

    assert first["category"] == second["category"]
    assert first["confidence"] == second["confidence"]
    assert first["selection_method"] == second["selection_method"]


def test_aggregate_deterministic_regardless_of_vote_insertion_order():
    base = {
        "llm": _vote("Database", 0.9, priority="high"),
        "knn": _vote("Network", 0.8),
        "centroid": _vote("Database", 0.85),
        "keyword": _vote("Network", 0.7),
    }
    # Same votes, different dict insertion orders.
    reordered = {
        "keyword": base["keyword"],
        "centroid": base["centroid"],
        "knn": base["knn"],
        "llm": base["llm"],
    }
    r1 = aggregate(base)
    r2 = aggregate(reordered)

    assert r1["category"] == r2["category"]
    assert r1["confidence"] == r2["confidence"]


def test_pick_winner_alphabetical_tiebreak():
    # Exact score tie -> alphabetical winner ("Database" < "Network").
    assert _pick_winner({"Database": 0.3, "Network": 0.3}) == "Database"
    # Reversed insertion order must give the same winner.
    assert _pick_winner({"Network": 0.3, "Database": 0.3}) == "Database"


def test_pick_winner_tie_stable_across_many_insertion_orders():
    import itertools

    cats = ["Database", "Network", "Application"]
    winners = set()
    for ordering in itertools.permutations(cats):
        scores = {c: 0.3 for c in ordering}  # all tied
        winners.add(_pick_winner(scores))
    # Tiebreak is alphabetical, so only one winner regardless of order.
    assert winners == {"Application"}


def test_pick_winner_returns_clear_highest_score():
    assert _pick_winner({"Database": 0.1, "Network": 0.9}) == "Network"


# ── Behavior 6: Weight renormalization ──────────────────────────────────────────

def test_get_weights_full_four_set_returns_tuned_weights():
    active = {
        "llm": _vote("X"),
        "knn": _vote("X"),
        "centroid": _vote("X"),
        "keyword": _vote("X"),
    }
    assert _get_weights(active) == WEIGHTS


def test_get_weights_knn_dropped_renormalizes_and_keeps_llm_dominant():
    # KNN dropped: this hits the renormalization fallback (not a named degraded set).
    active = {
        "llm": _vote("X"),
        "centroid": _vote("X"),
        "keyword": _vote("X"),
    }
    weights = _get_weights(active)

    # Weights renormalize to ~1.0 over the active set.
    assert abs(sum(weights.values()) - 1.0) < 1e-9
    # LLM stays dominant — NOT a uniform 0.333 split.
    assert weights["llm"] > weights["keyword"]
    assert weights["llm"] > 1.0 / 3
    # Tuned proportions preserved relative to each other.
    assert weights["centroid"] > weights["keyword"]


def test_get_weights_no_llm_uses_named_degraded_set():
    # knn+centroid+keyword (no llm) -> named DEGRADED_WEIGHTS["no_llm"].
    active = {
        "knn": _vote("X"),
        "centroid": _vote("X"),
        "keyword": _vote("X"),
    }
    weights = _get_weights(active)
    assert weights["centroid"] > weights["knn"]
    assert weights["centroid"] > weights["keyword"]
    assert abs(sum(weights.values()) - 1.0) < 1e-9


# ── Behavior 7: Confidence always in [0, 1] across scenarios ─────────────────────

def test_confidence_within_bounds_across_scenarios():
    scenarios = [
        # Unanimous
        {
            "llm": _vote("Database", 0.9, priority="high"),
            "knn": _vote("Database", 0.8),
            "centroid": _vote("Database", 0.85),
            "keyword": _vote("Database", 0.7),
        },
        # Supermajority 3/1
        {
            "llm": _vote("Database", 0.9, priority="high"),
            "knn": _vote("Database", 0.8),
            "centroid": _vote("Database", 0.85),
            "keyword": _vote("Network", 0.7),
        },
        # 2v2 split
        {
            "llm": _vote("Database", 0.6, priority="medium"),
            "knn": _vote("Network", 0.6),
            "centroid": _vote("Database", 0.6),
            "keyword": _vote("Network", 0.6),
        },
        # Total disagreement
        {
            "llm": _vote("Database", 0.5, priority="low"),
            "knn": _vote("Network", 0.5),
            "centroid": _vote("Application", 0.5),
            "keyword": _vote("Security", 0.5),
        },
        # Single classifier
        {
            "llm": _vote("Database", 0.9, priority="high"),
        },
    ]
    for votes in scenarios:
        for quality in ("HIGH", "MEDIUM", "LOW"):
            result = aggregate(votes, quality_score=quality)
            assert 0.0 <= result["confidence"] <= 1.0, (votes, quality, result)
