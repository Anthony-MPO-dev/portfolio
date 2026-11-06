"""Lead use case: the contact form. The WhatsApp number shows up only for hiring leads that were saved."""

import pytest

from app.services.lead import LeadService
from tests.fakes import FakeFormCounter, FakeLeadSink

WHATSAPP = "+00 00 00000-0000"  # placeholder; the real number lives only in CONTACT_WHATSAPP
FORM = {
    "name": "Jane Doe",
    "company": "Acme",
    "email": "jane@acme.com",
    "linkedin": "",
    "kind": "hiring",
    "page_lang": "en",
    "client_key": "client-a",
    "honeypot": "",
}


def make(sink: FakeLeadSink | None = None, max_per_day: int = 3):
    sink = sink or FakeLeadSink()
    service = LeadService(sink=sink, counter=FakeFormCounter(), whatsapp=WHATSAPP, max_per_day=max_per_day)
    return service, sink


def submit(sink: FakeLeadSink | None = None, **changes):
    service, sink = make(sink)
    return service.submit(**{**FORM, **changes}), sink


def test_hiring_lead_is_saved_and_gets_the_whatsapp_number():
    result, sink = submit()
    assert (result.status, result.whatsapp, sink.saved[0].email) == ("ok", WHATSAPP, "jane@acme.com")


def test_project_lead_is_saved_without_the_whatsapp_number():
    result, sink = submit(kind="project")
    assert (result.status, result.whatsapp, len(sink.saved)) == ("ok", None, 1)


@pytest.mark.parametrize("field", ["name", "company", "email"])
def test_missing_required_field_is_rejected_and_nothing_is_saved(field):
    result, sink = submit(**{field: "  "})
    assert (result.status, sink.saved) == ("invalid", [])


@pytest.mark.parametrize("email", ["jane", "jane@", "jane@acme", "ja ne@acme.com"])
def test_malformed_email_is_rejected(email):
    assert submit(email=email)[0].status == "invalid"


def test_field_longer_than_allowed_is_rejected():
    assert submit(name="x" * 101)[0].status == "invalid"


def test_unknown_kind_is_rejected():
    assert submit(kind="spam")[0].status == "invalid"


@pytest.mark.parametrize(
    "pasted",
    ["https://www.linkedin.com/in/jane-doe/", "linkedin.com/in/jane-doe", "https://br.linkedin.com/in/jane-doe"],
)
def test_linkedin_profile_is_saved_as_one_clean_url(pasted):
    _, sink = submit(linkedin=pasted)
    assert sink.saved[0].linkedin == "https://www.linkedin.com/in/jane-doe"


def test_link_that_is_not_a_linkedin_profile_is_rejected():
    assert submit(linkedin="https://evil.example/in/jane")[0].status == "invalid"


def test_fields_are_saved_trimmed_with_the_page_language():
    _, sink = submit(name="  Jane Doe ", page_lang="pt")
    assert (sink.saved[0].name, sink.saved[0].page_lang) == ("Jane Doe", "pt")


def test_unsupported_page_language_is_saved_as_english():
    _, sink = submit(page_lang="<script>")
    assert sink.saved[0].page_lang == "en"


def test_lead_that_could_not_be_saved_never_gets_the_number():
    result, _ = submit(FakeLeadSink(down=True))
    assert (result.status, result.whatsapp) == ("unavailable", None)


def test_bot_that_fills_the_hidden_field_is_silently_dropped():
    result, sink = submit(honeypot="https://spam.example")
    assert (result.status, result.whatsapp, sink.saved) == ("ok", None, [])


def test_fourth_valid_form_from_the_same_ip_in_a_day_is_rate_limited():
    service, sink = make()
    statuses = [service.submit(**FORM).status for _ in range(4)]
    assert (statuses, len(sink.saved)) == (["ok", "ok", "ok", "rate_limited"], 3)


def test_invalid_forms_do_not_use_up_the_daily_limit():
    service, _ = make(max_per_day=1)
    service.submit(**{**FORM, "email": "bad"})
    assert service.submit(**FORM).status == "ok"


def test_form_limit_is_per_ip():
    service, _ = make(max_per_day=1)
    service.submit(**FORM)
    assert service.submit(**{**FORM, "client_key": "client-b"}).status == "ok"
