"""Webhook POST through one keep-alive pool, with a timeout and a circuit breaker.

Responsibility: every alert to Anthony's personal n8n (lead and security) goes through the same urllib3 pool (no new
connection per call), waits at most 5 s and gets no retries; after 3 failures in a row the webhook is skipped for
30 s. Any failure, an error status or a skipped call raises OSError, which the alert adapters treat as "alert down".
Public API: Poster (callable with url and body).
Used by: app.main (N8nAlert and N8nSecurityAlert).
Depends on: urllib3, app.breaker.
Tests: tests/test_http_post.py.
"""

import urllib3

from app.breaker import CircuitBreaker, CircuitOpen

TIMEOUT = urllib3.Timeout(total=5)
HEADERS = {"Content-Type": "application/json", "User-Agent": "portfolio-api/1"}


class Poster:
    def __init__(self, pool=None, breaker: CircuitBreaker | None = None):
        self.pool = pool or urllib3.PoolManager(maxsize=2)
        self.breaker = breaker or CircuitBreaker()

    def __call__(self, url: str, body: bytes) -> None:
        try:
            self.breaker.call(self._post, url, body)
        except CircuitOpen as error:
            raise OSError("webhook skipped: circuit open") from error
        except urllib3.exceptions.HTTPError as error:
            raise OSError(f"webhook failed: {error.__class__.__name__}") from error

    def _post(self, url: str, body: bytes) -> None:
        response = self.pool.request("POST", url, body=body, headers=HEADERS, timeout=TIMEOUT, retries=False)
        if not 200 <= response.status < 300:
            raise OSError(f"webhook answered {response.status}")
