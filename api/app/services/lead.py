"""Lead use case: the contact form behind "Talk to Anthony".

Responsibility: drop bot submissions (hidden honeypot field filled), validate the form, cap valid forms per
client per day, save the lead (which also alerts Anthony), and release the WhatsApp number only to hiring leads
that were saved. The number comes from configuration and never passes through the model.
Public API: LeadService.submit, LeadResult.
Used by: the lead route.
Depends on: app.ports (Lead, LeadSink, LeadUnavailable, FormCounter), app.lang.
Tests: tests/test_lead.py.
"""

import re
from dataclasses import dataclass
from typing import Literal

from app.lang import page_lang as supported_lang
from app.ports import FormCounter, Lead, LeadSink, LeadUnavailable

EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
LINKEDIN = re.compile(r"(?:https?://)?(?:[a-z]{2,3}\.)?linkedin\.com/in/([\w%-]+)/?", re.IGNORECASE)
MAX_LEN = {"name": 100, "company": 100, "email": 254, "linkedin": 200}
KINDS = ("hiring", "project")


@dataclass(frozen=True)
class LeadResult:
    status: Literal["ok", "invalid", "rate_limited", "unavailable"]
    whatsapp: str | None = None


class LeadService:
    def __init__(self, sink: LeadSink, counter: FormCounter, whatsapp: str, max_per_day: int = 3):
        self.sink = sink
        self.counter = counter
        self.whatsapp = whatsapp
        self.max_per_day = max_per_day

    def submit(
        self,
        *,
        name: str,
        company: str,
        email: str,
        linkedin: str,
        kind: str,
        page_lang: str,
        client_key: str,
        honeypot: str = "",
    ) -> LeadResult:
        if honeypot.strip():
            return LeadResult("ok")  # look successful so the bot moves on

        fields = {"name": name.strip(), "company": company.strip(), "email": email.strip(), "linkedin": linkedin.strip()}
        if (
            not (fields["name"] and fields["company"] and EMAIL.fullmatch(fields["email"]))
            or any(len(value) > MAX_LEN[key] for key, value in fields.items())
            or kind not in KINDS
        ):
            return LeadResult("invalid")

        profile = None
        if fields["linkedin"]:
            match = LINKEDIN.fullmatch(fields["linkedin"])
            if not match:
                return LeadResult("invalid")
            profile = f"https://www.linkedin.com/in/{match.group(1)}"

        if self.counter.hit_form(client_key) > self.max_per_day:
            return LeadResult("rate_limited")

        lead = Lead(fields["name"], fields["company"], fields["email"], profile, kind, supported_lang(page_lang))
        try:
            self.sink.save(lead)
        except LeadUnavailable:
            return LeadResult("unavailable")
        return LeadResult("ok", self.whatsapp if kind == "hiring" else None)
