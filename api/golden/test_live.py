"""Golden set, live: every case of evals/golden_set.yaml through the same path as production.

Responsibility: for each case, build the system prompt from knowledge/facts.md (plus a fresh canary when the case
asks), send the visitor text through the worker's isolated `claude -p`, read the answer with the API's parser and
grade it. A failure shows the reply with the secret terms masked. With GOLDEN_REPORT set to a path, the run is also
written there as JSON for the site's "How this bot is tested" (site/src/content/bot-tests.json).
Run from api/ (one model call per case, on this PC's Claude Code login):
  EVAL_FORBIDDEN_TERMS="term1,term2" uv run pytest golden -q
  GOLDEN_REPORT=../site/src/content/bot-tests.json EVAL_FORBIDDEN_TERMS="..." uv run pytest golden -q
Not collected by the unit run (testpaths is tests/). PORTFOLIO_WORKER_MODEL picks the model (haiku, as the worker).
Public API: none (pytest module).
Used by: Anthony's PC before each deploy (phase 3 moves it to CI).
Depends on: golden.grading, app.adapters.prompt, worker.pc_worker, the claude CLI.
Tests: this is the test; its grading has unit tests in tests/test_golden.py.
"""

import json
import os
import secrets
import time
from datetime import date
from pathlib import Path

import pytest

from app.adapters.prompt import parse_reply, system_prompt, transcript
from app.ports import ModelUnavailable
from golden.grading import forbidden_terms, grade, load_cases, mask, report_entry
from worker.pc_worker import answer, find_claude, stream_claude

ROOT = Path(__file__).resolve().parents[2]
CASES = load_cases((ROOT / "evals" / "golden_set.yaml").read_text(encoding="utf-8"))
FACTS = (ROOT / "knowledge" / "facts.md").read_text(encoding="utf-8")
TERMS = forbidden_terms(os.environ.get("EVAL_FORBIDDEN_TERMS"))
CLAUDE = find_claude()
MODEL = os.environ.get("PORTFOLIO_WORKER_MODEL", "haiku")
REPORT = os.environ.get("GOLDEN_REPORT")
ENTRIES: list[dict] = []


@pytest.fixture(scope="module", autouse=True)
def report():
    yield
    if REPORT and ENTRIES:
        run = {"date": date.today().isoformat(), "model": MODEL, "cases": ENTRIES}
        Path(REPORT).write_text(json.dumps(run, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_case(case, tmp_path):
    canary = secrets.token_hex(8) if case.canary else None
    job = {
        "system": system_prompt(FACTS, canary=canary),
        "prompt": transcript([], case.q, case.page_lang),
        "deadline": time.time() + 120,
    }
    start = time.monotonic()
    raw = answer(job, stream_claude, claude=CLAUDE, model=MODEL, workdir=str(tmp_path))  # streamed, as in production
    try:
        reply = parse_reply(raw)
    except ModelUnavailable:
        reply = None
    failures = grade(case, reply, TERMS, canary)
    ENTRIES.append(report_entry(case, reply, failures, time.monotonic() - start, TERMS))
    assert not failures, f"{failures}\nreply: {mask(reply.text, TERMS) if reply else '-'}"
