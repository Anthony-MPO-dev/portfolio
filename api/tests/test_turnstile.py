"""Turnstile: a new conversation needs Cloudflare's proof of a real browser; an outage at Cloudflare doesn't close
the chat."""

import json
from types import SimpleNamespace

import urllib3

from app.adapters.turnstile import VERIFY_URL, TurnstileCheck


class FakePool:
    def __init__(self, answer=None, error=None):
        self.answer, self.error, self.sent = answer, error, []

    def request(self, method, url, body=None, headers=None, timeout=None, retries=None):
        self.sent.append((method, url, json.loads(body)))
        if self.error:
            raise self.error
        return SimpleNamespace(status=200, data=json.dumps(self.answer).encode())


def test_a_token_cloudflare_confirms_passes_and_the_secret_goes_with_it():
    pool = FakePool({"success": True})
    assert TurnstileCheck("SECRET", pool=pool)("token-1") is True
    assert pool.sent == [("POST", VERIFY_URL, {"secret": "SECRET", "response": "token-1"})]


def test_a_token_cloudflare_rejects_fails():
    assert TurnstileCheck("SECRET", pool=FakePool({"success": False, "error-codes": ["invalid-input-response"]}))("x") is False


def test_no_token_fails_without_asking_cloudflare():
    pool = FakePool({"success": True})
    assert TurnstileCheck("SECRET", pool=pool)(None) is False and TurnstileCheck("SECRET", pool=pool)("") is False
    assert pool.sent == []


def test_when_cloudflare_cannot_be_reached_the_conversation_still_starts():
    check = TurnstileCheck("SECRET", pool=FakePool(error=urllib3.exceptions.ConnectTimeoutError("timed out")))
    assert check("token") is True
