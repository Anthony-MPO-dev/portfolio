"""Redaction before a question is logged: contact details go, ordinary numbers stay."""

import pytest

from app.redact import redact


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("mail me at jane.doe@acme.com please", "mail me at [email] please"),
        ("call +55 (11) 91234-5678 today", "call [phone] today"),
        ("my number is 11912345678", "my number is [phone]"),
        ("US: +1 415-555-0100", "US: [phone]"),
    ],
)
def test_contact_details_are_replaced(text, expected):
    assert redact(text) == expected


@pytest.mark.parametrize(
    "text", ["He studied from 2020 to 2025", "3x faster, 13 of 23", "MAE 0.0205", "between 2020 2025"]
)
def test_ordinary_numbers_are_kept(text):
    assert redact(text) == text
