"""Unit tests for Mindy's rule-based intent parser.

Locks in the test-plan J-suite gaps: J1 ("show me my open tickets" must scope
to the asking user), J6/J10 (count and resolution-time questions must hit the
stats intent so they get deterministic, non-LLM answers).
"""
from backend.services.chat_intent import parse_intent


def test_my_open_tickets_is_scoped_ticket_list():
    # J1 — the most natural first question anyone asks a support bot
    intent = parse_intent("show me my open tickets")
    assert intent["intent"] == "ticket_list"
    assert intent["entities"].get("mine") is True
    assert intent["entities"].get("status") == "routed"  # "open" maps to routed


def test_tickets_i_raised_is_scoped():
    intent = parse_intent("list the tickets I raised")
    assert intent["intent"] == "ticket_list"
    assert intent["entities"].get("mine") is True


def test_all_tickets_is_not_scoped():
    intent = parse_intent("show all escalated tickets")
    assert intent["intent"] == "ticket_list"
    assert intent["entities"].get("mine") is None
    assert intent["entities"].get("status") == "escalated"


def test_escalated_count_is_stats():
    # J6 — must go to stats (deterministic template), not the LLM
    intent = parse_intent("how many tickets are escalated right now")
    assert intent["intent"] == "stats"


def test_resolution_time_is_stats():
    # J10 — resolution-time questions are stats
    intent = parse_intent("what's the average resolution time for Network this week")
    assert intent["intent"] == "stats"


def test_ticket_lookup_by_id_still_works():
    intent = parse_intent("what is the status of ticket #42")
    assert intent["intent"] == "ticket_lookup"
    assert intent["entities"]["ticket_id"] == "42"


def test_unknown_question_falls_through_to_general():
    intent = parse_intent("why is the sky blue")
    assert intent["intent"] == "general_it"
