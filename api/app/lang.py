"""Page language: the only languages the site has, and the fallback for anything else.

Responsibility: turn whatever language code the page sent into a supported one.
Public API: SUPPORTED, page_lang.
Used by: app.services.chat, app.services.lead.
Depends on: nothing.
Tests: tests/test_chat.py and tests/test_lead.py (unsupported language cases).
"""

SUPPORTED = ("en", "pt")


def page_lang(value: str) -> str:
    return value if value in SUPPORTED else "en"
