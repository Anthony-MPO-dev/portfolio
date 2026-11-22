"""Use case: the resume and cover letter pair the chat hands out (.claude/docs/plan-resume.md).

Responsibility: only inside an open chat session (it already passed the browser proof), give the standard pair at
once, or, with a job post, a pair tailored by the writer: within the visitor's and the site's daily limits and the
chat's daily budget, checked by app.resume.check_draft, kept for that session (an hour) under a random token, with an
alert to Anthony (company, role, language; never the post or the files). Past a limit, or when the writer fails or its
draft is refused, the standard pair comes instead, and the status says why. The standard pairs render once.
Public API: ResumeService, ResumeResult, ResumeLimits.
Used by: app.http (/api/resume). Depends on: app.ports (SessionStore, ResumeFiles, ResumeWriter, ModelUnavailable),
app.resume. Tests: tests/test_resume_service.py, tests/test_http.py.
"""

import logging
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from app.ports import ModelUnavailable, ResumeFiles, ResumeWriter, SessionStore
from app.resume import check_draft, render_letter, render_resume

log = logging.getLogger(__name__)
MAX_JOB = 8000  # characters of a pasted job post
KINDS = ("resume", "letter")
Status = Literal["ok", "standard", "fallback", "rate_limited", "invalid", "no_session"]


@dataclass(frozen=True)
class ResumeLimits:
    visitor_day: int = 3
    site_day: int = 50
    budget_day: float = 0.25  # US$, the chat's: one daily spend counter for both (main passes the chat's value)


@dataclass(frozen=True)
class ResumeResult:
    status: Status
    token: str | None = None
    lang: str = "en"
    company: str = ""
    role: str = ""


class ResumeService:
    def __init__(
        self,
        sessions: SessionStore,
        files: ResumeFiles,
        writer: ResumeWriter | None,
        bases: dict,
        allowed: set[str],
        limits: ResumeLimits = ResumeLimits(),
        alert: Callable[[str, str, str], None] = lambda company, role, lang: None,
    ):
        self.sessions, self.files, self.writer, self.bases = sessions, files, writer, bases
        self.allowed, self.limits, self.alert = allowed, limits, alert
        self.standard = {
            lang: dict(zip(KINDS, (render_resume(bases[lang], bases["name"], bases["contact"]), render_letter(bases[lang], bases["name"], bases["contact"]))))
            for lang in ("en", "pt")
        }  # fmt: skip

    def _open(self, sid: str | None) -> bool:
        return bool(sid) and self.sessions.session_exists(sid)

    def pair(self, sid: str | None, client_key: str, job: str, page_lang: str) -> ResumeResult:
        if not self._open(sid):
            return ResumeResult("no_session")
        job, lang = job.strip(), page_lang if page_lang in self.standard else "en"
        if len(job) > MAX_JOB:
            return ResumeResult("invalid")
        standard = f"standard-{lang}"
        if not job or self.writer is None:
            return ResumeResult("standard", standard, lang)
        # the visitor's count first: one visitor past their limit doesn't use up the site's
        if self.files.hit_visitor(client_key) > self.limits.visitor_day or self.files.hit_site() > self.limits.site_day:
            return ResumeResult("rate_limited", standard, lang)
        if self.sessions.spend_today() >= self.limits.budget_day:
            return ResumeResult("rate_limited", standard, lang)
        try:
            lang, draft = self.writer.tailor(job)
        except ModelUnavailable:
            return ResumeResult("fallback", standard, lang)
        base = self.bases[lang]
        if reason := check_draft(draft, base, self.allowed):
            log.warning("resume draft refused: %s", reason)  # the reason only, never the text
            return ResumeResult("fallback", standard, lang)
        token = secrets.token_urlsafe(16)
        name, contact = self.bases["name"], self.bases["contact"]
        self.files.put(sid, token, {"resume": render_resume(base, name, contact, draft), "letter": render_letter(base, name, contact, draft)})
        self.alert(draft.company, draft.role, lang)
        return ResumeResult("ok", token, lang, draft.company, draft.role)

    def file(self, sid: str | None, token: str, kind: str) -> bytes | None:
        if kind not in KINDS or not self._open(sid):
            return None
        if token.startswith("standard-"):
            pair = self.standard.get(token.removeprefix("standard-"))
            return pair[kind] if pair else None
        return self.files.get(sid, token, kind)
