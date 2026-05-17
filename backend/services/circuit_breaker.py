"""Lightweight async circuit breaker for Ollama calls.

States:
    CLOSED  — normal operation, requests pass through
    OPEN    — fast-fail, skip Ollama entirely (after fail_max consecutive failures)
    HALF_OPEN — allow one test request to check if Ollama recovered

Config:
    fail_max=3, reset_timeout=30s
"""

import logging
import time
from enum import Enum

logger = logging.getLogger(__name__)


class State(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(self, name: str = "ollama", fail_max: int = 3, reset_timeout: float = 30.0):
        self.name = name
        self.fail_max = fail_max
        self.reset_timeout = reset_timeout

        self._state = State.CLOSED
        self._fail_count = 0
        self._last_failure_time = 0.0
        self._success_count = 0

    @property
    def state(self) -> State:
        """Current state, auto-transitioning OPEN → HALF_OPEN after reset_timeout."""
        if self._state == State.OPEN:
            if time.time() - self._last_failure_time >= self.reset_timeout:
                self._state = State.HALF_OPEN
                logger.info("Circuit breaker [%s]: OPEN → HALF_OPEN (testing recovery)", self.name)
        return self._state

    @property
    def is_available(self) -> bool:
        """Whether requests should be attempted."""
        s = self.state
        return s in (State.CLOSED, State.HALF_OPEN)

    def record_success(self) -> None:
        """Record a successful call."""
        prev = self._state
        self._fail_count = 0
        self._state = State.CLOSED
        if prev != State.CLOSED:
            logger.info("Circuit breaker [%s]: %s → CLOSED (recovered)", self.name, prev.value)

    def record_failure(self) -> None:
        """Record a failed call."""
        self._fail_count += 1
        self._last_failure_time = time.time()

        if self._state == State.HALF_OPEN:
            # Test request failed — back to OPEN
            self._state = State.OPEN
            logger.warning("Circuit breaker [%s]: HALF_OPEN → OPEN (test failed)", self.name)
        elif self._fail_count >= self.fail_max:
            prev = self._state
            self._state = State.OPEN
            logger.warning(
                "Circuit breaker [%s]: %s → OPEN (%d consecutive failures)",
                self.name, prev.value, self._fail_count,
            )

    def get_status(self) -> dict:
        """Return status info for health/debug endpoints."""
        return {
            "state": self.state.value,
            "fail_count": self._fail_count,
            "fail_max": self.fail_max,
            "reset_timeout": self.reset_timeout,
            "seconds_since_last_failure": round(time.time() - self._last_failure_time, 1) if self._last_failure_time else None,
        }


# Singleton instance for Ollama
ollama_breaker = CircuitBreaker(name="ollama", fail_max=3, reset_timeout=30.0)
