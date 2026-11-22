"""The canned engine for local end-to-end tests (MODEL_ENGINE=demo): fixed lines, no model, no cost."""

from pathlib import Path

import pytest

from app.adapters.demo_engine import DemoModel, DemoResumeWriter
from app.main import build
from app.ports import ModelReply
from app.resume import allowed_numbers, check_draft, load
from tests.test_main import ENV, FACTS

ROOT = Path(__file__).resolve().parents[2]
BASES = load(ROOT / "knowledge" / "resume.yaml", {})


def final(message: str) -> ModelReply:
    return [p for p in DemoModel().stream([], message, "en") if isinstance(p, ModelReply)][0]


def test_asking_for_the_resume_ends_with_the_resume_line_and_talking_to_anthony_with_the_contact_line():
    assert final("so send me his resume in pdf").offer_resume is True
    assert final("I want to talk to Anthony").offer_contact is True
    plain = final("What is his stack?")
    assert (plain.offer_contact, plain.offer_resume) == (False, False) and plain.text


def test_the_demo_draft_passes_the_real_check_and_follows_the_post_language():
    lang, draft = DemoResumeWriter(BASES["en"]).tailor("Acme is hiring an AI Engineer")
    assert lang == "en" and check_draft(draft, BASES["en"], allowed_numbers("", BASES)) is None
    assert DemoResumeWriter(BASES["en"]).tailor("Vaga de engenheiro de IA para nossa equipe")[0] == "pt"


def test_the_demo_engine_builds_without_the_worker_routes():
    paths = {route.path for route in build({**ENV, "MODEL_ENGINE": "demo"}, FACTS).routes}
    assert "/api/resume" in paths and "/api/worker/next" not in paths


def test_an_unknown_engine_is_still_refused():
    from app.main import ConfigError

    with pytest.raises(ConfigError, match="MODEL_ENGINE"):
        build({**ENV, "MODEL_ENGINE": "gpt"}, FACTS)
