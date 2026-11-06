"""Redaction: strip contact details from a visitor's question before it is logged.

Responsibility: replace e-mail addresses with [email] and phone numbers (9+ digits) with [phone], keeping
ordinary numbers such as years, ratios and metrics.
Public API: redact.
Used by: app.services.chat.
Depends on: nothing.
Tests: tests/test_redact.py.
"""

import re

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
NUMBER_RUN = re.compile(r"(?<![\w+])\+?\(?\d[\d\s().-]{6,}\d")
PHONE_MIN_DIGITS = 9


def _phone(match: re.Match[str]) -> str:
    run = match.group()
    return "[phone]" if sum(c.isdigit() for c in run) >= PHONE_MIN_DIGITS else run


def redact(text: str) -> str:
    return NUMBER_RUN.sub(_phone, EMAIL.sub("[email]", text))
