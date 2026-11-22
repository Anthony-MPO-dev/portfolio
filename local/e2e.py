"""End-to-end run on the local copy (local/compose.yaml, http://localhost:8088): a real Chrome drives the real site and
API, with the demo engine and Cloudflare's test keys. Needs Playwright for Python and Chrome installed.
    python local/e2e.py [w=390]
Checks, in order: the resume panel opens under the answer; both PDFs download, the resume with the private location
and the letter without it; the rain covers the page; a pasted job post tailors the pair; the contact form, opened
and then followed by another message, keeps that message in view; a hiring lead gets the number. Exit 1 on any miss.
"""

import re
import subprocess
import sys
import zlib
from pathlib import Path

from playwright.sync_api import sync_playwright

SITE = "http://localhost:8088/"
WIDTH = int(next((a.split("=")[1] for a in sys.argv[1:] if a.startswith("w=")), "390"))
failures: list[str] = []


def check(name: str, ok: bool) -> None:
    print(("ok   " if ok else "FAIL ") + name)
    if not ok:
        failures.append(name)


def pdf_text(data: bytes) -> str:
    """The text of an fpdf2 PDF: its content streams are zlib-compressed, the text in plain parentheses."""
    streams = re.findall(rb"stream\r?\n(.*?)\r?\nendstream", data, re.S)
    out = []
    for raw in streams:
        try:
            out.append(zlib.decompress(raw).decode("latin-1"))
        except zlib.error:
            pass
    return " ".join("".join(re.findall(r"\((.*?)(?<!\\)\)", s)) for s in out)


def download(page, selector: str) -> tuple[bytes, bool]:
    """The file's bytes, and whether the rain fell (looked for at once: the layer is gone 2.3 s later)."""
    with page.expect_download() as got:
        page.click(selector)
    rain = page.locator(".rain-burst").count() > 0
    return open(got.value.path(), "rb").read(), rain


def ask(page, text: str) -> None:
    box = page.locator(".chat-composer textarea")
    box.fill(text)
    box.press("Enter")


# a fresh start: the local copy's Redis holds only test data, and its daily limits (3 tailorings) would stop a rerun
COMPOSE = str(Path(__file__).with_name("compose.yaml"))
subprocess.run(["docker", "compose", "-f", COMPOSE, "exec", "-T", "redis", "redis-cli", "FLUSHALL"], check=True, capture_output=True)

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome")
    page = browser.new_page(viewport={"width": WIDTH, "height": 820}, accept_downloads=True)
    page.goto(SITE)
    page.click(".chat-launcher")

    ask(page, "so send me his resume in pdf")
    page.wait_for_selector(".chat-resume", timeout=30_000)
    check("the resume panel opens under the answer", page.evaluate(
        "() => document.querySelector('.chat-resume').previousElementSibling.classList.contains('bot')"))

    resume, rain = download(page, ".chat-download >> nth=0")
    check("the resume downloads, with the private location", resume.startswith(b"%PDF") and "Testville" in pdf_text(resume))
    check("the rain covers the page", rain)
    letter, _ = download(page, ".chat-download >> nth=1")
    check("the letter downloads, without the private location", letter.startswith(b"%PDF") and "Testville" not in pdf_text(letter))

    page.fill(".chat-resume-job textarea", "Acme is hiring an AI Engineer to build LLM support agents.")
    page.click(".chat-resume-job button")
    page.wait_for_function("() => document.querySelector('.chat-resume-note').textContent.includes('Demo Company')", timeout=30_000)
    tailored, _ = download(page, ".chat-download >> nth=1")
    check("a job post tailors the pair", "demo draft" in pdf_text(tailored))

    ask(page, "I want to talk to Anthony")
    page.wait_for_selector(".chat-talk", timeout=30_000)
    page.click(".chat-talk")
    page.wait_for_selector(".chat-lead")
    ask(page, "are you still there?")
    page.wait_for_function("() => [...document.querySelectorAll('.chat-msg.bot .chat-text')].length >= 3", timeout=30_000)
    check("a message sent with the form open stays in view", page.evaluate("""() => {
        const log = document.querySelector('.chat-log').getBoundingClientRect();
        const last = [...document.querySelectorAll('.chat-msg')].at(-1).getBoundingClientRect();
        return last.bottom <= log.bottom + 1 && last.top >= log.top - 1; }"""))

    page.fill(".chat-lead input[name=name]", "Test Recruiter")
    page.fill(".chat-lead input[name=company]", "Test Co")
    page.fill(".chat-lead input[name=email]", "recruiter@example.com")
    page.check(".chat-lead input[value=hiring]")
    page.click(".chat-lead button[type=submit]")
    page.wait_for_selector(".chat-notice a[href^='https://wa.me/']", timeout=30_000)
    check("a hiring lead gets the number", True)
    check("no sideways scroll", not page.evaluate("document.documentElement.scrollWidth > innerWidth"))
    browser.close()

print(f"{'FAILED: ' + ', '.join(failures) if failures else 'all passed'} (width {WIDTH})")
sys.exit(1 if failures else 0)
