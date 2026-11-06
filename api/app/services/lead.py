"""Lead use case: the contact form behind "Talk to Anthony".

Responsibility: validate the form, save the lead (which also alerts Anthony), and release the WhatsApp number
only to hiring leads that were saved. The number comes from configuration and never passes through the model.
Public API: LeadService.submit, LeadResult.
Used by: the lead route.
Depends on: app.ports (Lead, LeadSink, LeadUnavailable), app.lang.
Tests: tests/test_lead.py.
"""

import re
from dataclasses import dataclass
from typing import Literal

from app.lang import page_lang as supported_lang
from app.ports import Lead, LeadSink, LeadUnavailable

EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
LINKEDIN = re.compile(r"(?:https?://)?(?:[a-z]{2,3}\.)?linkedin\.com/in/([\w%-]+)/?", re.IGNORECASE)
MAX_LEN = {"name": 100, "company": 100, "email": 254, "linkedin": 200}
KINDS = ("hiring", "project")


@dataclass(frozen=True)
class LeadResult:
    status: Literal["ok", "invalid", "unavailable"]
    whatsapp: str | None = None


class LeadService:
    def __init__(self, sink: LeadSink, whatsapp: str):
        self.sink = sink
        self.whatsapp = whatsapp

    def submit(self, *, name: str, company: str, email: str, linkedin: str, kind: str, page_lang: str) -> LeadResult:
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

        lead = Lead(fields["name"], fields["company"], fields["email"], profile, kind, supported_lang(page_lang))
        try:
            self.sink.save(lead)
        except LeadUnavailable:
            return LeadResult("unavailable")
        return LeadResult("ok", self.whatsapp if kind == "hiring" else None)
