"""Unit tests for the Ollama circuit breaker.

All tests construct fresh CircuitBreaker instances; the global
``ollama_breaker`` singleton is never mutated.
"""

import time

from backend.services.circuit_breaker import CircuitBreaker, State


def test_starts_closed_and_available():
    cb = CircuitBreaker(name="test", fail_max=3, reset_timeout=30.0)
    assert cb.state == State.CLOSED
    assert cb.is_available is True


def test_state_is_deterministic_when_idle():
    cb = CircuitBreaker(name="test", fail_max=3, reset_timeout=30.0)
    # Repeated reads with no events must not change anything.
    assert cb.state == State.CLOSED
    assert cb.state == State.CLOSED
    assert cb.is_available is True


def test_failures_below_threshold_stay_closed():
    cb = CircuitBreaker(name="test", fail_max=3, reset_timeout=30.0)
    cb.record_failure()
    cb.record_failure()  # 2 < fail_max(3)
    assert cb.state == State.CLOSED
    assert cb.is_available is True


def test_reaching_fail_max_opens_and_is_unavailable():
    cb = CircuitBreaker(name="test", fail_max=3, reset_timeout=30.0)
    for _ in range(3):
        cb.record_failure()
    assert cb.state == State.OPEN
    assert cb.is_available is False


def test_fail_max_of_one_opens_after_single_failure():
    cb = CircuitBreaker(name="test", fail_max=1, reset_timeout=30.0)
    cb.record_failure()
    assert cb.state == State.OPEN
    assert cb.is_available is False


def test_record_success_resets_failure_count():
    cb = CircuitBreaker(name="test", fail_max=3, reset_timeout=30.0)
    cb.record_failure()
    cb.record_failure()
    cb.record_success()
    # Failure count reset, so it now takes a full fail_max again to open.
    cb.record_failure()
    cb.record_failure()
    assert cb.state == State.CLOSED
    assert cb.is_available is True


def test_record_success_closes_an_open_breaker():
    cb = CircuitBreaker(name="test", fail_max=3, reset_timeout=30.0)
    for _ in range(3):
        cb.record_failure()
    assert cb.state == State.OPEN

    cb.record_success()
    assert cb.state == State.CLOSED
    assert cb.is_available is True


def test_open_transitions_to_half_open_after_reset_timeout():
    cb = CircuitBreaker(name="test", fail_max=2, reset_timeout=0.05)
    cb.record_failure()
    cb.record_failure()
    assert cb.state == State.OPEN
    assert cb.is_available is False

    time.sleep(0.06)  # let reset_timeout elapse

    # Reading state auto-transitions OPEN -> HALF_OPEN.
    assert cb.state == State.HALF_OPEN
    assert cb.is_available is True


def test_half_open_failure_returns_to_open():
    cb = CircuitBreaker(name="test", fail_max=2, reset_timeout=0.05)
    cb.record_failure()
    cb.record_failure()
    time.sleep(0.06)
    assert cb.state == State.HALF_OPEN

    # A failed test request while HALF_OPEN trips back to OPEN.
    cb.record_failure()
    assert cb.state == State.OPEN
    assert cb.is_available is False


def test_half_open_success_recovers_to_closed():
    cb = CircuitBreaker(name="test", fail_max=2, reset_timeout=0.05)
    cb.record_failure()
    cb.record_failure()
    time.sleep(0.06)
    assert cb.state == State.HALF_OPEN

    cb.record_success()
    assert cb.state == State.CLOSED
    assert cb.is_available is True


def test_open_stays_open_before_timeout():
    cb = CircuitBreaker(name="test", fail_max=2, reset_timeout=30.0)
    cb.record_failure()
    cb.record_failure()
    # No time elapsed relative to a 30s timeout.
    assert cb.state == State.OPEN
    assert cb.is_available is False


def test_get_status_reports_consistent_fields():
    cb = CircuitBreaker(name="test", fail_max=3, reset_timeout=30.0)
    status = cb.get_status()
    assert status["state"] == State.CLOSED.value
    assert status["fail_count"] == 0
    assert status["fail_max"] == 3
    assert status["reset_timeout"] == 30.0
    assert status["seconds_since_last_failure"] is None

    cb.record_failure()
    status = cb.get_status()
    assert status["fail_count"] == 1
    assert status["seconds_since_last_failure"] is not None
