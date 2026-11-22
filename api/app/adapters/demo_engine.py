"""A canned engine for local end-to-end tests (MODEL_ENGINE=demo; Anthony, 22/11: the local copy runs on a fake model,
never the paid API). Never set it in production: the bot would answer fixed lines.

Responsibility: stand in for the model and the resume writer with no network and no cost, so the whole site, the API,
Redis and Postgres can be driven in a browser. The chat streams one fixed line per kind of message (asking for the
resume ends with the resume line, asking to talk to Anthony with the contact line); the writer returns a draft
built from the base's first ids, which passes the real check, in the job post's language.
Public API: DemoModel (a ChatModel), DemoResumeWriter (a ResumeWriter).
Used by: app.main. Depends on: app.adapters.prompt (parse_reply, the markers), app.resume (Draft).
Tests: tests/test_demo_engine.py.
"""

import re
from collections.abc import Iterator, Sequence

from app.adapters.prompt import CONTACT, RESUME, parse_reply
from app.ports import Attachment, ModelReply, Turn
from app.resume import Draft

PORTUGUESE = re.compile(r"\b(vaga|equipe|desenvolvedor|engenheiro|você|currículo|empresa)\b", re.IGNORECASE)


class DemoModel:
    def stream(
        self, history: list[Turn], message: str, page_lang: str, attachments: Sequence[Attachment] = ()
    ) -> Iterator[str | ModelReply]:
        asked = message.lower()
        if re.search(r"resum|\bcv\b|curr[ií]cul|cover letter", asked):
            raw = f"Demo engine: both are just below this answer. Paste a job post to tailor them.\n{RESUME}"
        elif re.search(r"talk|contact|hire|falar|contato", asked):
            raw = f"Demo engine: leave your details below and Anthony will get back to you.\n{CONTACT}"
        else:
            raw = "Demo engine: Anthony is an AI and backend engineer who works in Python, FastAPI and LLM agents."
        yield raw.split("\n")[0]
        yield parse_reply(raw)


class DemoResumeWriter:
    def __init__(self, base: dict):
        self.base = base

    def tailor(self, job: str) -> tuple[str, Draft]:
        lang = "pt" if PORTUGUESE.search(job) else "en"
        return lang, Draft(
            company="Demo Company",
            role="Demo Role",
            to="",
            summary="AI and backend engineer with 3+ years of Python who puts LLM agents in production.",
            opening="This is a demo draft from the local test engine.",
            match="It picks the base's first ids, so every line it prints is approved text.",
            bullets={r["id"]: [b["id"] for b in r["bullets"][:2]] for r in self.base["roles"]},
            projects=[p["id"] for p in self.base["projects"][:2]],
            skills=[s["id"] for s in self.base["skills"]],
        )
