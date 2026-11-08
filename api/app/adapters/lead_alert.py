"""Lead alert: save the lead, then tell Anthony through his personal n8n (which sends it to his Telegram).

Responsibility: SaveThenAlert is the LeadSink the lead use case gets. The lead counts as saved once the database has
it; if the alert then fails, the lead stays saved, the visitor still gets an answer and the failure is logged.
N8nAlert posts the lead as JSON to the webhook URL from configuration (Anthony's personal n8n, never a work one).
Public API: SaveThenAlert, N8nAlert.
Used by: the API composition (app.main).
Depends on: app.ports (Lead, LeadSink, LeadUnavailable), a poster (app.http_post.Poster in production: pooled, with a timeout and a breaker).
Tests: tests/test_lead_alert.py.
"""

import json
import logging
from collections.abc import Callable
from dataclasses import asdict

from app.ports import Lead, LeadSink, LeadUnavailable

log = logging.getLogger(__name__)


class N8nAlert:
    def __init__(self, url: str, post: Callable[[str, bytes], None]):
        self.url = url
        self.post = post

    def save(self, lead: Lead) -> None:
        try:
            self.post(self.url, json.dumps(asdict(lead), ensure_ascii=False).encode())
        except OSError as error:
            raise LeadUnavailable() from error


class SaveThenAlert:
    def __init__(self, store: LeadSink, alert: LeadSink):
        self.store = store
        self.alert = alert

    def save(self, lead: Lead) -> None:
        self.store.save(lead)
        try:
            self.alert.save(lead)
        except LeadUnavailable:
            log.warning("lead saved, but the alert to Anthony failed")
