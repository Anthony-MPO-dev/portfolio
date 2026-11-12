"""Circuit breaker for calls outside the API process (the n8n webhook, Postgres).

Responsibility: after `failures` errors in a row, refuse the call at once with CircuitOpen for `cooldown` seconds, so
the caller's plan B (the e-mail fallback, skipping the question log) runs without waiting on a dead service; then let
one trial call through: a success closes the circuit, a failure opens it again. Thread-safe (sync routes run in a
thread pool).
Public API: CircuitBreaker, CircuitOpen.
Used by: app.http_post, app.adapters.postgres, app.adapters.anthropic_model, app.adapters.turnstile.
Depends on: the standard library.
Tests: tests/test_breaker.py.
"""

import threading
import time
from collections.abc import Callable


class CircuitOpen(Exception):
    """The service failed too often lately; the call was skipped."""


class CircuitBreaker:
    def __init__(self, failures: int = 3, cooldown: float = 30.0, clock: Callable[[], float] = time.monotonic):
        self.failures, self.cooldown, self.clock = failures, cooldown, clock
        self.count, self.opened_at = 0, None
        self.lock = threading.Lock()

    def call(self, fn, *args, **kwargs):
        with self.lock:
            if self.opened_at is not None and self.clock() - self.opened_at < self.cooldown:
                raise CircuitOpen()
        try:
            result = fn(*args, **kwargs)
        except Exception:
            with self.lock:
                self.count += 1
                if self.count >= self.failures:
                    self.opened_at = self.clock()
            raise
        with self.lock:
            self.count, self.opened_at = 0, None
        return result
