"""Security alert: tells Anthony when the output guard blocks a reply or the worker drops a run that wasn't clean.

Responsibility: post {"kind": "security", "alert": reason} to his personal n8n webhook (the same one as the lead
alert; the workflow picks the Telegram text by kind), at most once per reason in a 10-minute window (a Redis key under
chat:*, so a burst of attacks is one message), and never break the chat: a failed alert is only logged. The reason is
a short label, never visitor text.
Public API: N8nSecurityAlert (callable with the reason), WINDOW.
Used by: app.main (ChatService on a guard hit, the worker route on a worker alert).
Depends on: redis-py, app.adapters.lead_alert._post.
Tests: tests/test_security_alert.py.
"""

import json
import logging
from collections.abc import Callable

import redis

from app.adapters.lead_alert import _post

log = logging.getLogger(__name__)
WINDOW = 600  # seconds: one message per reason per window


class N8nSecurityAlert:
    def __init__(self, url: str, r: redis.Redis, post: Callable[[str, bytes], None] = _post):
        self.url, self.redis, self.post = url, r, post

    def __call__(self, reason: str) -> None:
        try:
            if not self.redis.set(f"chat:alert:{reason}", 1, nx=True, ex=WINDOW):
                return
            self.post(self.url, json.dumps({"kind": "security", "alert": reason}).encode())
        except (OSError, redis.RedisError) as error:
            log.warning("security alert failed (%s): %s", error.__class__.__name__, reason)
