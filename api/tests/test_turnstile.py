"""Turnstile: a new conversation needs Cloudflare's proof of a real browser; an outage at Cloudflare doesn't close
the chat."""

import json
from types import SimpleNamespace

import urllib3

from app.adapters.turnstile import VERIFY_URL, TurnstileCheck


class FakePool:
    def __init__(self, answer=None, error=None, status=200):
        self.answer, self.error, self.status, self.sent = answer, error, status, []

    def request(self, method, url, body=None, headers=None, timeout=None, retries=None):
        self.sent.append((method, url, json.loads(body)))
        if self.error:
            raise self.error
        return SimpleNamespace(status=self.status, data=json.dumps(self.answer or {}).encode())


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


def test_a_token_cloudflare_refuses_as_a_bad_request_fails_and_never_opens_the_breaker():
    check = TurnstileCheck("SECRET", pool=FakePool({"success": False}, status=400))
    assert [check("odd-token") for _ in range(5)] == [False] * 5


def test_an_error_on_cloudflare_s_side_lets_the_conversation_start():
    assert TurnstileCheck("SECRET", pool=FakePool({"success": False}, status=503))("token") is True
    internal = FakePool({"success": False, "error-codes": ["internal-error"]})
    assert TurnstileCheck("SECRET", pool=internal)("token") is True


def test_a_wrong_secret_is_logged_and_does_not_close_the_chat(caplog):
    wrong = FakePool({"success": False, "error-codes": ["invalid-input-secret"]})
    assert TurnstileCheck("SECRET", pool=wrong)("token") is True
    assert "invalid-input-secret" in caplog.text


def test_an_expired_or_reused_token_fails():
    used = FakePool({"success": False, "error-codes": ["timeout-or-duplicate"]})
    assert TurnstileCheck("SECRET", pool=used)("token") is False
