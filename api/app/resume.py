"""Resume and cover letter PDFs for the chat (.claude/docs/plan-resume.md).

Responsibility: load the public base (knowledge/resume.yaml) with the private parts filled in (RESUME_PRIVATE on the
server: city, places, the credit fund's name; public fallbacks without it); check a tailoring draft (known ids only,
every role kept, no number the facts and the base don't have, the output guard's rules, capped lengths); and render the
resume and the letter as PDFs. Every bullet, project and paragraph prints as approved in the base; a draft only picks
and orders the ids and writes the summary and the letter's opening. Without a draft, the standard pair.
Public API: load, Draft, allowed_numbers, check_draft, render_resume, render_letter.
Used by: app.services.resume. Depends on: fpdf2, PyYAML, app.output_guard.
Tests: tests/test_resume.py.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from fpdf import FPDF

from app.output_guard import check as guard

FALLBACK = {
    "location": "Brazil", "loc_insight": "Brazil", "credit_fund": "Credit fund (FIDC)", "loc_credit_fund": "Brazil",
    "loc_fapemat": "Brazil", "support_employer": "IT services company", "loc_support": "Brazil",
}  # fmt: skip
LIMITS = {"company": 80, "role": 80, "to": 80, "summary": 600, "opening": 400, "match": 400}
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
PLACEHOLDER = re.compile(r"\{(\w+)\}")
# fpdf2's built-in fonts take Latin-1 only; the model writes typographic quotes and dashes now and then
PLAIN = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": ",", "…": "...", "•": "-"})


@dataclass(frozen=True)
class Draft:
    company: str
    role: str
    to: str
    summary: str
    opening: str
    match: str
    bullets: dict[str, list[str]]  # role id -> its bullet ids, in the order to print
    projects: list[str]
    skills: list[str]


def _fill(node, values: dict[str, str]):
    if isinstance(node, str):
        return PLACEHOLDER.sub(lambda m: values.get(m[1], m[0]), node)  # the letter's {to}, {role}... stay for render
    if isinstance(node, list):
        return [_fill(n, values) for n in node]
    if isinstance(node, dict):
        return {k: _fill(v, values) for k, v in node.items()}
    return node


def load(path: Path, private: dict[str, str]) -> dict:
    return _fill(yaml.safe_load(path.read_text(encoding="utf-8")), {**FALLBACK, **private})


def _norm(number: str) -> str:
    return number.replace(",", ".")


def allowed_numbers(facts: str, base: dict) -> set[str]:
    """The numbers a draft may use: every one the facts or the base already say."""
    return {_norm(n) for n in NUMBER.findall(facts + str(base))}


def check_draft(draft: Draft, base: dict, allowed: set[str]) -> str | None:
    roles = {r["id"]: {b["id"] for b in r["bullets"]} for r in base["roles"]}
    if any(rid not in roles or not set(ids) <= roles[rid] for rid, ids in draft.bullets.items()):
        return "unknown id"
    if not set(draft.projects) <= {p["id"] for p in base["projects"]} or not set(draft.skills) <= {s["id"] for s in base["skills"]}:
        return "unknown id"
    if any(not draft.bullets.get(rid) for rid in roles):
        return "empty role"
    if any(len(getattr(draft, field)) > cap for field, cap in LIMITS.items()):
        return "too long"
    for field in LIMITS:
        if reason := guard(getattr(draft, field), ""):
            return reason
    written = " ".join((draft.summary, draft.opening, draft.match))
    if not {_norm(n) for n in NUMBER.findall(written)} <= allowed:
        return "number"
    return None


class _Page(FPDF):
    def __init__(self):
        super().__init__(format="A4")
        self.set_margins(18, 16, 18)
        self.set_auto_page_break(True, 16)
        self.add_page()

    def line_of(self, text: str, size: float, style: str = "", gap: float = 0.5, grey: bool = False):
        self.set_font("Helvetica", style, size)
        self.set_text_color(90 if grey else 15)
        self.multi_cell(0, size * 0.5, text.translate(PLAIN), align="L", new_x="LMARGIN", new_y="NEXT")
        self.ln(gap)

    def heading(self, text: str):
        self.ln(2.5)
        self.line_of(text.upper(), 10, "B", 0.5)
        self.set_draw_color(15)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(2)

    def bullet(self, text: str):
        self.set_font("Helvetica", "", 9.5)
        self.set_text_color(15)
        self.cell(4, 4.75, "-")
        self.multi_cell(0, 4.75, text.translate(PLAIN), align="L", new_x="LMARGIN", new_y="NEXT")
        self.ln(0.8)

    def head(self, name: str, base: dict, contact: str, size: float):
        self.line_of(name, size, "B", 1)
        self.line_of(base["title"], 11.5, "", 1)
        self.line_of(contact, 9, grey=True)
        self.line_of(base["location"], 9, grey=True, gap=2)


def _by_id(items: list[dict], ids: list[str] | None) -> list[dict]:
    return items if ids is None else [next(i for i in items if i["id"] == wanted) for wanted in ids]


def render_resume(base: dict, name: str, contact: str, draft: Draft | None = None) -> bytes:
    pdf, h = _Page(), base["headings"]
    pdf.head(name, base, contact, 20)
    pdf.heading(h["summary"])
    pdf.line_of(draft.summary if draft else base["summary"], 9.5)
    pdf.heading(h["experience"])
    for role in base["roles"]:
        pdf.line_of(role["title"], 10.5, "B", 0.3)
        pdf.line_of(f"{role['where']} · {role['when']}", 9, grey=True, gap=0.3)
        if role["note"]:
            pdf.line_of(role["note"], 9, "I", 0.8, grey=True)
        for bullet in _by_id(role["bullets"], draft.bullets[role["id"]] if draft else None):
            pdf.bullet(bullet["text"])
        pdf.ln(1.5)
    pdf.heading(h["projects"])
    for project in _by_id(base["projects"], draft.projects if draft else None):
        pdf.bullet(project["text"])
    pdf.heading(h["skills"])
    for group in _by_id(base["skills"], draft.skills if draft else None):
        pdf.line_of(f"{group['label']}: {group['items']}", 9.5, gap=0.8)
    pdf.heading(h["education"])
    for line in base["education"]:
        pdf.line_of(line, 9.5, gap=0.8)
    pdf.heading(h["languages"])
    pdf.line_of(base["languages"], 9.5)
    return bytes(pdf.output())


def render_letter(base: dict, name: str, contact: str, draft: Draft | None = None) -> bytes:
    letter = base["letter"]
    pdf = _Page()
    pdf.head(name, base, contact, 16)
    pdf.ln(4)
    pdf.line_of(letter["greeting"].replace("{to}", draft.to if draft and draft.to else letter["to_default"]), 10.5, gap=3)
    intro = letter["intro_standard"]
    if draft:
        intro = letter["intro_tailored"].replace("{role}", draft.role).replace("{company}", draft.company).replace("{opening}", draft.opening)
    for paragraph in [intro, *([draft.match] if draft and draft.match else []), *letter["body"]]:
        pdf.line_of(paragraph, 10.5, gap=3)
    pdf.line_of(letter["closing"], 10.5, gap=1)
    pdf.line_of(name, 10.5, "B")
    return bytes(pdf.output())
