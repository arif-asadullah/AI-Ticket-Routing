"""Unit tests for KNN classifier (Classifier 3).

Verifies weighted-vote voting and the recent fix where confidence is the
WEIGHTED vote share (winner_weighted_score / total_weighted_score), not the
old count/k value.
"""

from backend.services.knn_classifier import classify_knn


def test_empty_list_returns_none_category_and_zero_confidence():
    result = classify_knn([])
    assert result["category"] is None
    assert result["confidence"] == 0.0
    assert result["neighbors"] == []
    assert result["vote_counts"] == {}


def test_all_neighbors_same_category_wins_with_full_confidence():
    tickets = [
        {"key": "1", "title": "a", "category": "Database", "similarity": 0.95},
        {"key": "2", "title": "b", "category": "Database", "similarity": 0.90},
        {"key": "3", "title": "c", "category": "Database", "similarity": 0.85},
    ]
    result = classify_knn(tickets)
    assert result["category"] == "Database"
    # Only one category present -> weighted share is exactly 1.0
    assert result["confidence"] == 1.0
    assert result["vote_counts"] == {"Database": 3}


def test_weighted_confidence_beats_old_count_based_value():
    # 3 Database @ 0.95 (=2.85) vs 2 Application @ 0.30 (=0.60); total = 3.45
    # Weighted winner share = 2.85 / 3.45 = 0.826...  (old count-based was 3/5 = 0.6)
    tickets = [
        {"key": "1", "title": "db1", "category": "Database", "similarity": 0.95},
        {"key": "2", "title": "db2", "category": "Database", "similarity": 0.95},
        {"key": "3", "title": "db3", "category": "Database", "similarity": 0.95},
        {"key": "4", "title": "app1", "category": "Application", "similarity": 0.30},
        {"key": "5", "title": "app2", "category": "Application", "similarity": 0.30},
    ]
    result = classify_knn(tickets)

    assert result["category"] == "Database"
    # Must reflect weighted share, clearly above the old count-based 0.6
    assert result["confidence"] > 0.6
    # Tight range derived directly from the code's formula (rounded to 3 dp)
    expected = round((0.95 * 3) / (0.95 * 3 + 0.30 * 2), 3)
    assert expected == 0.826
    assert result["confidence"] == expected
    # Unweighted counts kept for transparency
    assert result["vote_counts"] == {"Database": 3, "Application": 2}


def test_confidence_always_in_unit_interval():
    cases = [
        [],
        [{"key": "1", "title": "x", "category": "Network", "similarity": 0.5}],
        [
            {"key": "1", "title": "x", "category": "A", "similarity": 0.99},
            {"key": "2", "title": "y", "category": "B", "similarity": 0.01},
        ],
        [
            {"key": "1", "title": "x", "category": "A", "similarity": 0.4},
            {"key": "2", "title": "y", "category": "B", "similarity": 0.4},
        ],
    ]
    for tickets in cases:
        result = classify_knn(tickets)
        assert 0.0 <= result["confidence"] <= 1.0


def test_k_limits_neighbors_considered():
    tickets = [
        {"key": str(i), "title": f"t{i}", "category": "Database", "similarity": 0.9}
        for i in range(10)
    ]
    result = classify_knn(tickets, k=3)
    assert len(result["neighbors"]) == 3
    # vote_counts must only reflect the top-k neighbors
    assert sum(result["vote_counts"].values()) == 3


def test_neighbors_payload_shape_and_title_truncation():
    long_title = "x" * 100
    tickets = [
        {"key": "42", "title": long_title, "category": "Database", "similarity": 0.777}
    ]
    result = classify_knn(tickets)
    neighbor = result["neighbors"][0]
    assert neighbor["key"] == "42"
    assert neighbor["category"] == "Database"
    assert len(neighbor["title"]) == 60  # title truncated to 60 chars
    assert neighbor["similarity"] == 0.777


def test_missing_similarity_uses_default_weight():
    # Ticket without 'similarity' should not crash; default weight (0.5) used.
    tickets = [{"key": "1", "title": "x", "category": "Database"}]
    result = classify_knn(tickets)
    assert result["category"] == "Database"
    assert 0.0 <= result["confidence"] <= 1.0


def test_all_neighbors_missing_category_returns_none():
    tickets = [
        {"key": "1", "title": "x", "similarity": 0.9},
        {"key": "2", "title": "y", "similarity": 0.8},
    ]
    result = classify_knn(tickets)
    assert result["category"] is None
    assert result["confidence"] == 0.0
    assert result["vote_counts"] == {}


def test_deterministic_across_repeated_calls():
    tickets = [
        {"key": "1", "title": "a", "category": "Database", "similarity": 0.95},
        {"key": "2", "title": "b", "category": "Application", "similarity": 0.30},
    ]
    first = classify_knn(tickets)
    second = classify_knn(tickets)
    assert first == second
