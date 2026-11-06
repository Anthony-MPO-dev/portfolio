"""Lead alert: the lead is saved first, then Anthony is alerted through his personal n8n (Telegram)."""

import json
import urllib.error

import pytest

from app.adapters.lead_alert import N8nAlert, SaveThenAlert
from app.ports import Lead, LeadUnavailable
from tests.fakes import FakeLeadSink

LEAD = Lead("Jane Doe", "Acme", "jane@acme.com", None, "hiring", "en")


def test_alert_goes_out_after_the_lead_is_saved():
    store, alert = FakeLeadSink(), FakeLeadSink()
    SaveThenAlert(store, alert).save(LEAD)
    assert (store.saved, alert.saved) == ([LEAD], [LEAD])


def test_lead_that_could_not_be_saved_raises_and_sends_no_alert():
    alert = FakeLeadSink()
    with pytest.raises(LeadUnavailable):
        SaveThenAlert(FakeLeadSink(down=True), alert).save(LEAD)
    assert alert.saved == []


def test_failed_alert_does_not_undo_a_saved_lead():
    store = FakeLeadSink()
    SaveThenAlert(store, FakeLeadSink(down=True)).save(LEAD)
    assert store.saved == [LEAD]


def test_n8n_gets_the_lead_as_json():
    sent = []
    N8nAlert("https://n8n.example/webhook/lead", post=lambda url, body: sent.append((url, json.loads(body)))).save(LEAD)
    assert sent == [
        (
            "https://n8n.example/webhook/lead",
            {"name": "Jane Doe", "company": "Acme", "email": "jane@acme.com", "linkedin": None, "kind": "hiring",
             "page_lang": "en"},
        )
    ]  # fmt: skip


def test_n8n_down_is_reported_as_unavailable():
    def post(url, body):
        raise urllib.error.URLError("connection refused")

    with pytest.raises(LeadUnavailable):
        N8nAlert("https://n8n.example/webhook/lead", post=post).save(LEAD)
