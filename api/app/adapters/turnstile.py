"""Cloudflare Turnstile: proof that a new conversation comes from a real browser, not a script calling the API.

Responsibility: send the token the page got from Turnstile to Cloudflare's siteverify, with the secret, and say whether
it passed. No token, a token Cloudflare refuses (success false, or a 4xx to an odd token) fails. When the fault is on
Cloudflare's side or ours (unreachable, a 5xx, "internal-error", a wrong secret) the conversation still starts and
the reason is logged: the visitor and site-wide limits keep holding, and a fault there shouldn't take the chat down.
Only those faults count toward the circuit breaker (3 in a row skip siteverify for 30 s). The visitor's IP isn't sent
(it's optional for siteverify).
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
FAULTS = {"internal-error", "missing-input-secret", "invalid-input-secret"}  # not the visitor's doing


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
            log.warning("Turnstile fault, letting the conversation start: %s", error)
            return True

    def _verify(self, token: str) -> bool:
        """True or False is the visitor's answer; an exception is a fault on Cloudflare's side or ours."""
        body = json.dumps({"secret": self.secret, "response": token}).encode()
        response = self.pool.request(
            "POST", VERIFY_URL, body=body, headers={"Content-Type": "application/json"}, timeout=TIMEOUT, retries=False
        )
        if response.status >= 500:
            raise OSError(f"siteverify answered {response.status}")
        if response.status != 200:
            return False  # a bad request: the token itself was odd
        answer = json.loads(response.data)
        if answer.get("success"):
            return True
        codes = answer.get("error-codes") or []
        if FAULTS.intersection(codes):
            raise OSError(f"siteverify error-codes {codes}")
        return False
