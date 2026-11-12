"""Golden set, live: every case of evals/golden_set.yaml through the same path as production.

Responsibility: for each case, build the system prompt from knowledge/facts.md (plus a fresh canary when the case
asks), send the visitor text through the worker's isolated `claude -p`, read the answer with the API's parser and
grade it. A failure shows the reply with the secret terms masked; a run error (the worker refusing a tool call, for
one) is a failure too, so no case drops out of the count. With GOLDEN_REPORT set to a path, a complete run is also
written there as JSON for the site's "How this bot is tested" (site/src/content/bot-tests.json); the author runs it
with ops/golden-report.ps1, which asks for the secret terms with the typing hidden.
Run from api/ (one model call per case). With ANTHROPIC_API_KEY set, each case goes through the production engine
(app.adapters.anthropic_model, Claude Haiku 5.5, about US$ 0.05 for the whole set); without it, through the worker's
`claude -p` on this PC's Claude Code login:
  EVAL_FORBIDDEN_TERMS="term1,term2" uv run pytest golden -q
  GOLDEN_REPORT=../site/src/content/bot-tests.json EVAL_FORBIDDEN_TERMS="..." uv run pytest golden -q
Not collected by the unit run (testpaths is tests/). PORTFOLIO_WORKER_MODEL picks the worker's model (haiku).
Public API: none (pytest module).
Used by: Anthony's PC before each deploy (phase 3 moves it to CI).
Depends on: golden.grading, app.adapters.prompt, app.adapters.anthropic_model (with a key), worker.pc_worker and the
claude CLI (without one).
Tests: this is the test; its grading has unit tests in tests/test_golden.py.
"""

import os
import secrets
import sys
import time
from datetime import date
from pathlib import Path

import pytest

from app.adapters.anthropic_model import LABEL, AnthropicModel
from app.adapters.prompt import parse_reply, system_prompt, transcript
from app.ports import ModelUnavailable
from golden.grading import forbidden_terms, grade, load_cases, mask, report_entry, report_json
from worker.pc_worker import answer, find_claude, stream_claude

ROOT = Path(__file__).resolve().parents[2]
CASES = load_cases((ROOT / "evals" / "golden_set.yaml").read_text(encoding="utf-8"))
FACTS = (ROOT / "knowledge" / "facts.md").read_text(encoding="utf-8")
TERMS = forbidden_terms(os.environ.get("EVAL_FORBIDDEN_TERMS"))
KEY = os.environ.get("ANTHROPIC_API_KEY")
CLAUDE = None if KEY else find_claude()
MODEL = LABEL if KEY else os.environ.get("PORTFOLIO_WORKER_MODEL", "haiku")
REPORT = os.environ.get("GOLDEN_REPORT")
ENTRIES: list[dict] = []


@pytest.fixture(scope="module", autouse=True)
def report():
    yield
    if not REPORT:
        return
    text = report_json(ENTRIES, len(CASES), date.today().isoformat(), MODEL)
    if text:
        Path(REPORT).write_text(text, encoding="utf-8")
    else:
        print(f"\ngolden report not written: {len(ENTRIES)} of {len(CASES)} cases ran", file=sys.stderr)


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_case(case, tmp_path):
    canary = secrets.token_hex(8) if case.canary else None
    job = {
        "system": system_prompt(FACTS, canary=canary),
        "prompt": transcript([], case.q, case.page_lang),
        "deadline": time.time() + 120,
    }
    reply, failures = None, ["run error"]  # replaced once the reply is graded
    try:
        try:
            if KEY:  # the production engine, streamed, with the contact line already taken out
                engine = AnthropicModel.connect(KEY, job["system"], workspace=os.environ.get("ANTHROPIC_WORKSPACE_ID"))
                reply = list(engine.stream([], case.q, case.page_lang))[-1]
            else:
                reply = parse_reply(answer(job, stream_claude, claude=CLAUDE, model=MODEL, workdir=str(tmp_path)))
        except ModelUnavailable:
            reply = None
        failures = grade(case, reply, TERMS, canary)
    finally:
        ENTRIES.append(report_entry(case, reply, failures, TERMS))
    assert not failures, f"{failures}\nreply: {mask(reply.text, TERMS) if reply else '-'}"
