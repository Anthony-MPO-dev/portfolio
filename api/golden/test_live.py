"""Golden set, live: every case of evals/golden_set.yaml through the same path as production.

Responsibility: for each case, build the system prompt from knowledge/facts.md (plus a fresh canary when the case
asks), send the visitor text through the worker's isolated `claude -p`, read the answer with the API's parser and
grade it. A failure shows the reply with the secret terms masked.
Run from api/ (one model call per case, on this PC's Claude Code login):
  EVAL_FORBIDDEN_TERMS="term1,term2" uv run pytest golden -q
Not collected by the unit run (testpaths is tests/). PORTFOLIO_WORKER_MODEL picks the model (haiku, as the worker).
Public API: none (pytest module).
Used by: Anthony's PC before each deploy (phase 3 moves it to CI).
Depends on: golden.grading, app.adapters.prompt, worker.pc_worker, the claude CLI.
Tests: this is the test; its grading has unit tests in tests/test_golden.py.
"""

import os
import secrets
import time
from pathlib import Path

import pytest

from app.adapters.prompt import REPLY_SCHEMA, parse_reply, system_prompt, transcript
from app.ports import ModelUnavailable
from golden.grading import forbidden_terms, grade, load_cases, mask
from worker.pc_worker import answer, find_claude, run_claude

ROOT = Path(__file__).resolve().parents[2]
CASES = load_cases((ROOT / "evals" / "golden_set.yaml").read_text(encoding="utf-8"))
FACTS = (ROOT / "knowledge" / "facts.md").read_text(encoding="utf-8")
TERMS = forbidden_terms(os.environ.get("EVAL_FORBIDDEN_TERMS"))
CLAUDE = find_claude()
MODEL = os.environ.get("PORTFOLIO_WORKER_MODEL", "haiku")


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_case(case, tmp_path):
    canary = secrets.token_hex(8) if case.canary else None
    job = {
        "system": system_prompt(FACTS, canary=canary),
        "prompt": transcript([], case.q, case.page_lang),
        "schema": REPLY_SCHEMA,
        "deadline": time.time() + 120,
    }
    raw = answer(job, run_claude, claude=CLAUDE, model=MODEL, workdir=str(tmp_path))
    try:
        reply = parse_reply(raw)
    except ModelUnavailable:
        reply = None
    failures = grade(case, reply, TERMS, canary)
    assert not failures, f"{failures}\nreply: {mask(reply.text, TERMS) if reply else '-'}"
