"""Cloudflare Turnstile: proof that a new conversation comes from a real browser, not a script calling the API.

Responsibility: send the token the page got from Turnstile to Cloudflare's siteverify, with the secret, and say whether
it passed. No token fails at once. If Cloudflare can't be reached (timeout, error, circuit open after 3 failures),
the conversation still starts: the per-visitor and site-wide limits keep holding, and an outage there shouldn't take
the chat down. The visitor's IP isn't sent (it's optional for siteverify).
Public API: TurnstileCheck (callable: token -> bool), VERIFY_URL.
Used by: app.main, when TURNSTILE_SECRET is set (wired into app.services.chat as `human`).
Depends on: urllib3, app.breaker.
Tests: tests/test_turnstile.py.
"""

import json
import logging

import urllib3

from app.breaker import CircuitBreaker, CircuitOpen

log = logging.getLogger(__name__)
VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
TIMEOUT = urllib3.Timeout(total=5)


class TurnstileCheck:
    def __init__(self, secret: str, pool=None, breaker: CircuitBreaker | None = None):
        self.secret = secret
        self.pool = pool or urllib3.PoolManager(maxsize=2)
        self.breaker = breaker or CircuitBreaker()

    def __call__(self, token: str | None) -> bool:
        if not token:
            return False
        try:
            return self.breaker.call(self._verify, token)
        except (CircuitOpen, urllib3.exceptions.HTTPError, OSError, ValueError) as error:
            log.warning("Turnstile unreachable, letting the conversation start: %s", error.__class__.__name__)
            return True

    def _verify(self, token: str) -> bool:
        body = json.dumps({"secret": self.secret, "response": token}).encode()
        response = self.pool.request(
            "POST", VERIFY_URL, body=body, headers={"Content-Type": "application/json"}, timeout=TIMEOUT, retries=False
        )
        if response.status != 200:
            raise OSError(f"siteverify answered {response.status}")
        return bool(json.loads(response.data).get("success"))
