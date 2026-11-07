"""Output guard: the model's reply is treated as hostile until checked (OWASP LLM05), outside the model.

Responsibility: name the first reason a reply can't reach the browser: the per-process canary (the prompt leaked),
a secret, a disk path, an email or phone number that isn't Anthony's public one, a Markdown image (the exfiltration
channel) or a link outside the allowlist. The page renders plain text and the site's CSP is the backstop; this
check keeps a hit from ever being shown or saved.
Public API: check.
Used by: app.services.chat (injected by app.main with this process's canary).
Depends on: the standard library re.
Tests: tests/test_output_guard.py.
"""

import re

ALLOWED_EMAILS = {"anthonympodev@gmail.com"}
ALLOWED_LINKS = ("anthonymuniz.dev", "github.com/anthony-mpo-dev", "linkedin.com/in/anthony-mpo-dev")
SECRET = re.compile(
    r"sk-ant-[\w-]{10,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_\w{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----"
)
PATH = re.compile(r"[A-Za-z]:\\(?:Users|Windows)\\|/home/[a-z_]|/Users/[A-Za-z]|\.claude[/\\]")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE = re.compile(r"\+?\d[\d ().-]{8,}\d")
IMAGE = re.compile(r"!\[[^\]]*\]\(")
URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)


def _allowed(url: str) -> bool:
    bare = re.sub(r"^(?:https?://)?(?:www\.)?", "", url.lower()).rstrip("/.,;:)")
    return any(bare == link or bare.startswith(link + "/") for link in ALLOWED_LINKS)


def check(reply: str, canary: str) -> str | None:
    if canary and canary.lower() in reply.lower():
        return "canary"
    if SECRET.search(reply):
        return "secret"
    if PATH.search(reply):
        return "path"
    if any(email.lower() not in ALLOWED_EMAILS for email in EMAIL.findall(reply)):
        return "email"
    if any(len(re.sub(r"\D", "", number)) >= 10 for number in PHONE.findall(reply)):
        return "phone"
    if IMAGE.search(reply):
        return "image"
    if any(not _allowed(url) for url in URL.findall(reply)):
        return "link"
    return None
