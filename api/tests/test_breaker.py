"""Circuit breaker: after 3 failures in a row the call is skipped for 30 s (the caller's plan B runs at once), then
one trial call decides whether it closes again."""

import pytest

from app.breaker import CircuitBreaker, CircuitOpen


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def boom():
    raise OSError("down")


def test_three_failures_open_the_circuit_and_later_calls_are_skipped():
    clock, calls = Clock(), []
    breaker = CircuitBreaker(failures=3, cooldown=30, clock=clock)
    for _ in range(3):
        with pytest.raises(OSError):
            breaker.call(boom)
    with pytest.raises(CircuitOpen):
        breaker.call(calls.append, "skipped")
    assert calls == []


def test_after_the_cooldown_one_success_closes_it_and_one_failure_reopens_it():
    clock = Clock()
    breaker = CircuitBreaker(failures=3, cooldown=30, clock=clock)
    for _ in range(3):
        with pytest.raises(OSError):
            breaker.call(boom)
    clock.now = 31
    assert breaker.call(lambda: "ok") == "ok"
    for _ in range(2):
        with pytest.raises(OSError):
            breaker.call(boom)
    assert breaker.call(lambda: "still closed") == "still closed"  # a success resets the count
    for _ in range(3):
        with pytest.raises(OSError):
            breaker.call(boom)
    clock.now = 62
    with pytest.raises(OSError):
        breaker.call(boom)  # the trial call fails
    with pytest.raises(CircuitOpen):
        breaker.call(lambda: "skipped again")
