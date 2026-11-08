"""Security alert: a hit of the output guard or of the worker's checks reaches Anthony through his personal n8n,
at most once per reason in a 10-minute window, and a failed alert never breaks the chat."""

import json

import fakeredis

from app.adapters.security_alert import WINDOW, N8nSecurityAlert

URL = "https://n8n.example/webhook/portfolio"


def make(post=None):
    sent, redis = [], fakeredis.FakeRedis(decode_responses=True)
    alert = N8nSecurityAlert(URL, redis, post=post or (lambda url, body: sent.append((url, json.loads(body)))))
    return alert, sent, redis


def test_each_reason_reaches_anthony_once_per_window():
    alert, sent, redis = make()
    alert("output guard: link")
    alert("output guard: link")
    alert("worker: tool_use")
    assert sent == [
        (URL, {"kind": "security", "alert": "output guard: link"}),
        (URL, {"kind": "security", "alert": "worker: tool_use"}),
    ]
    assert 0 < redis.ttl("chat:alert:output guard: link") <= WINDOW == 600


def test_a_failed_alert_is_logged_and_never_raised(caplog):
    def down(url, body):
        raise OSError("n8n down")

    alert, _, _ = make(post=down)
    alert("output guard: canary")
    assert "security alert failed" in caplog.text
