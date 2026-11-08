"""Pooled webhook POST: one keep-alive pool for every alert, a 5-second timeout, and a circuit breaker; any failure
is an OSError, which the alert adapters already treat as "alert down"."""

import pytest
import urllib3

from app.http_post import Poster


class FakePool:
    def __init__(self, *outcomes):
        self.outcomes, self.calls = list(outcomes), []

    def request(self, method, url, body=None, headers=None, timeout=None, retries=None):
        self.calls.append((method, url, body, timeout))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return type("R", (), {"status": outcome})()


def test_a_post_goes_through_the_shared_pool_with_a_timeout():
    pool = FakePool(200)
    Poster(pool=pool)("https://n8n.example/hook", b"{}")
    method, url, body, timeout = pool.calls[0]
    assert (method, url, body) == ("POST", "https://n8n.example/hook", b"{}") and timeout.total == 5


@pytest.mark.parametrize("outcome", [500, urllib3.exceptions.NewConnectionError(None, "refused")])
def test_an_error_status_or_a_network_error_is_an_oserror(outcome):
    with pytest.raises(OSError):
        Poster(pool=FakePool(outcome))("https://n8n.example/hook", b"{}")


def test_after_three_failures_the_webhook_is_left_alone_for_a_while():
    pool = FakePool(500, 500, 500, 200)
    post = Poster(pool=pool)
    for _ in range(4):
        with pytest.raises(OSError):
            post("https://n8n.example/hook", b"{}")
    assert len(pool.calls) == 3
