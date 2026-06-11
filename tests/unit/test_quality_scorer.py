"""Unit tests for backend.services.quality_scorer.score_quality.

Scoring model (from source):
  - servers OR services entities present: +3
  - error_codes present:                 +3
  - len(description.strip()) > 100:       +2  (elif > 40: +1)
  - any technical keyword in text:        +1
  - len(title.strip()) > 15:              +1
  Mapping: score >= 5 -> HIGH, score >= 3 -> MEDIUM, else LOW.
"""

from backend.services.quality_scorer import score_quality

VALID_LEVELS = {"HIGH", "MEDIUM", "LOW"}


def _entities(servers=None, services=None, error_codes=None):
    return {
        "servers": list(servers or []),
        "services": list(services or []),
        "error_codes": list(error_codes or []),
    }


def test_rich_ticket_is_high():
    # server entity (+3) + long desc >100 (+2) + tech keyword "timeout" (+1)
    # + title >15 chars (+1) = 7 -> HIGH
    title = "Database replication failing on prod"  # >15 chars
    description = (
        "The primary database server prod-db-01 is reporting a connection "
        "timeout during replication and the replica is now lagging badly "
        "behind, causing stale reads across the application tier."
    )  # >100 chars, contains tech keywords
    entities = _entities(servers=["prod-db-01"])

    assert score_quality(title, description, entities) == "HIGH"


def test_vague_short_ticket_is_low():
    # title "help" (4 chars, +0), "Something is broken" has no tech keyword,
    # desc len 19 (<=40, +0), no entities -> score 0 -> LOW
    title = "help"
    description = "Something is broken"
    entities = _entities()

    assert score_quality(title, description, entities) == "LOW"


def test_medium_ticket():
    # server entity alone (+3), short generic title (<=15, +0),
    # short desc with no tech keyword (+0) -> score 3 -> MEDIUM
    title = "DB issue"
    description = "It acts up sometimes."
    entities = _entities(servers=["prod-db-01"])

    assert score_quality(title, description, entities) == "MEDIUM"


def test_result_is_always_a_valid_literal():
    cases = [
        ("", "", _entities()),
        ("help", "Something is broken", _entities()),
        ("DB issue", "It acts up.", _entities(servers=["x"])),
        (
            "Database replication failing on prod",
            "connection timeout during replication " * 5,
            _entities(servers=["prod-db-01"], error_codes=["ORA-12541"]),
        ),
        ("a" * 200, "b" * 500, _entities()),
    ]
    for title, description, entities in cases:
        result = score_quality(title, description, entities)
        assert result in VALID_LEVELS, (title, description, result)


def test_error_codes_present_boosts_score():
    # Same base ticket. Without error codes the score stays below the
    # next tier; adding error_codes (+3) raises the quality level.
    title = "issue"  # <=15 chars, +0
    description = "It happens."  # short, no tech keyword, +0
    without_codes = _entities()  # score 0 -> LOW
    with_codes = _entities(error_codes=["ORA-12541"])  # +3 -> MEDIUM

    assert score_quality(title, description, without_codes) == "LOW"
    assert score_quality(title, description, with_codes) == "MEDIUM"


def test_error_codes_alone_reach_at_least_medium():
    # error_codes (+3) guarantees score >= 3, i.e. at least MEDIUM.
    title = "x"
    description = "y"
    result = score_quality(title, description, _entities(error_codes=["E500"]))
    assert result in {"MEDIUM", "HIGH"}


def test_scoring_is_deterministic():
    title = "Database replication failing on prod"
    description = (
        "The primary database server prod-db-01 is reporting a connection "
        "timeout during replication and the replica is now lagging badly."
    )
    entities = _entities(servers=["prod-db-01"], error_codes=["ORA-12541"])

    results = {score_quality(title, description, entities) for _ in range(5)}
    assert results == {"HIGH"}


def test_empty_input_does_not_crash_and_is_low():
    assert score_quality("", "", _entities()) == "LOW"


def test_services_entity_treated_like_servers():
    # services (not servers) also grants the +3 entity signal.
    title = "svc"
    description = "ok"
    result = score_quality(title, description, _entities(services=["payments-api"]))
    assert result == "MEDIUM"  # +3 only -> MEDIUM
