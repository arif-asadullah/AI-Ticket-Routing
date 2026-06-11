"""Unit tests for backend.services.keyword_classifier.classify_keyword.

Pure-function tests: no DB, Redis, Ollama, or network required.
"""

from backend.services.keyword_classifier import classify_keyword

VALID_CATEGORIES = {
    "Infrastructure",
    "Application",
    "Database",
    "Network",
    "Security",
    "Access Management",
}


def test_database_text_classified_as_database():
    result = classify_keyword("postgresql replication lag connection pool")
    assert result["category"] == "Database"


def test_network_text_classified_as_network():
    result = classify_keyword("vpn dns firewall")
    assert result["category"] == "Network"


def test_return_shape_has_documented_keys():
    result = classify_keyword("postgresql query slow")
    assert set(result.keys()) == {"category", "confidence", "scores"}
    assert isinstance(result["scores"], dict)
    # scores has an entry for every known category
    assert set(result["scores"].keys()) == VALID_CATEGORIES


def test_returned_category_is_one_of_six_valid_categories():
    result = classify_keyword("vpn dns firewall tls bgp")
    assert result["category"] in VALID_CATEGORIES


def test_confidence_in_unit_interval_when_category_returned():
    result = classify_keyword("postgresql replication deadlock vacuum wal")
    assert result["category"] is not None
    assert 0.0 <= result["confidence"] <= 1.0


def test_word_boundary_substring_does_not_false_positive():
    # "dns" is a single-word Network keyword; "dnsmasq" must NOT match it
    # via word-boundary matching. With no other keywords present the text
    # should score zero everywhere.
    result = classify_keyword("dnsmasq configuration tweak")
    assert result["scores"]["Network"] == 0


def test_word_boundary_accessibility_does_not_trigger_access_match():
    # "accessibility" alone must not produce an Access Management match.
    # ("access" is not even a standalone keyword, and the multi-word
    # phrases like "access review" require the literal phrase.)
    result = classify_keyword("accessibility audit for the dashboard")
    assert result["scores"]["Access Management"] == 0


def test_word_boundary_real_keyword_does_match():
    # Sanity check the other direction: a standalone "dns" token DOES match.
    result = classify_keyword("the dns server is unreachable")
    assert result["scores"]["Network"] >= 1


def test_empty_text_returns_valid_dict_without_crashing():
    result = classify_keyword("")
    assert set(result.keys()) == {"category", "confidence", "scores"}
    assert result["category"] is None
    assert result["confidence"] == 0.0
    assert all(v == 0 for v in result["scores"].values())


def test_garbage_text_returns_valid_dict_without_crashing():
    result = classify_keyword("zzz qqq @@@ 123 ###")
    assert set(result.keys()) == {"category", "confidence", "scores"}
    assert result["category"] is None
    assert result["confidence"] == 0.0


def test_case_insensitive_matching():
    lower = classify_keyword("postgresql replication")
    upper = classify_keyword("POSTGRESQL REPLICATION")
    assert lower["category"] == upper["category"] == "Database"
    assert lower["scores"] == upper["scores"]


def test_multi_word_phrase_substring_match():
    # "connection pool" is a multi-word phrase matched as a substring.
    result = classify_keyword("the connection pool is exhausted")
    assert result["scores"]["Database"] >= 1


def test_deterministic_across_repeated_calls():
    text = "vpn dns firewall postgresql query"
    first = classify_keyword(text)
    second = classify_keyword(text)
    assert first == second


def test_confidence_equals_winner_score_over_total():
    # Two clean Network keywords, no other matches -> confidence 1.0.
    result = classify_keyword("vpn firewall")
    assert result["category"] == "Network"
    assert result["confidence"] == 1.0
