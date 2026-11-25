import io
from pathlib import Path

import pytest
from pypdf import PdfReader

from app.resume import FALLBACK, Draft, allowed_numbers, check_draft, load, render_letter, render_resume

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = {"location": "Testville, Brazil", "credit_fund": "Fund X FIDC", "support_employer": "Shop Y"}
BASE = load(ROOT / "knowledge" / "resume.yaml", PRIVATE)
ALLOWED = allowed_numbers((ROOT / "knowledge" / "facts.md").read_text(encoding="utf-8"), BASE)


def text_of(pdf: bytes) -> str:
    return " ".join(" ".join((page.extract_text() or "").split()) for page in PdfReader(io.BytesIO(pdf)).pages)


def draft(**changes) -> Draft:
    fields = {
        "company": "Acme",
        "role": "AI Engineer",
        "to": "Engineering Manager",
        "summary": "AI and backend engineer with 3+ years of Python, focused on LLM agents in production.",
        "opening": "Your team is moving support to LLM agents, which is what I do every day.",
        "match": "You ask for RAG and LLM evaluation, and I shipped both in production.",
        "bullets": {"insight": ["evaluation", "search-fix"], "credit": ["capacity"], "fapemat": ["models"], "support": ["repair"]},
        "projects": ["portfolio"],
        "skills": ["ai", "backend", "async", "data", "ops"],
    }
    return Draft(**{**fields, **changes})


def test_both_languages_carry_the_same_ids():
    def ids(lang):
        b = BASE[lang]
        return ([(r["id"], [x["id"] for x in r["bullets"]]) for r in b["roles"]], [p["id"] for p in b["projects"]], [s["id"] for s in b["skills"]])

    assert ids("en") == ids("pt")


def test_private_values_fill_the_placeholders_and_public_fallbacks_stand_in_without_them():
    assert "Testville, Brazil" in BASE["en"]["location"] and "Fund X FIDC" in BASE["en"]["roles"][1]["where"]
    bare = str(load(ROOT / "knowledge" / "resume.yaml", {}))
    assert not any("{" + key + "}" in bare for key in FALLBACK) and "Brazil · Open to remote roles" in bare


def test_the_standard_resume_prints_the_approved_text_and_the_private_location_but_no_phone():
    pdf = render_resume(BASE["en"], BASE["name"], BASE["contact"])
    text = text_of(pdf)
    assert pdf.startswith(b"%PDF") and "AI & Backend Engineer" in text and "Testville, Brazil" in text
    assert "3x faster" in text and "13 of 23" in text and "+55" not in text


def test_a_tailored_resume_keeps_only_the_chosen_bullets_in_their_order():
    text = text_of(render_resume(BASE["en"], BASE["name"], BASE["contact"], draft()))
    assert text.index("transcript-only review") < text.index("13 of 23")
    assert "3x faster" not in text and "focused on LLM agents in production" in text


def test_the_letters_open_with_the_standard_intro_or_the_tailored_one():
    standard = text_of(render_letter(BASE["en"], BASE["name"], BASE["contact"]))
    tailored = text_of(render_letter(BASE["en"], BASE["name"], BASE["contact"], draft()))
    assert "Dear Hiring Manager" in standard and "Dear Engineering Manager" in tailored
    assert "AI Engineer role at Acme" in tailored and "You ask for RAG" in tailored


def test_the_letter_carries_no_private_data_only_the_resume_does():
    letter = text_of(render_letter(BASE["en"], BASE["name"], BASE["contact"]))
    assert "Fund X FIDC" not in letter and "Testville" not in letter and "worked at a credit fund" in letter
    assert "Fund X FIDC" in text_of(render_resume(BASE["en"], BASE["name"], BASE["contact"]))


def test_a_post_without_company_or_role_keeps_the_standard_intro_and_adds_the_opening():
    text = text_of(render_letter(BASE["en"], BASE["name"], BASE["contact"], draft(company="", role="")))
    assert "role at ." not in text and "looking for a remote, full-time role" in text and "Your team is moving" in text


def test_a_role_read_from_the_post_cannot_expand_into_another_field():
    text = text_of(render_letter(BASE["en"], BASE["name"], BASE["contact"], draft(role="{opening}")))
    assert "the {opening} role at Acme" in text


def test_the_portuguese_pair_renders_with_accents():
    text = text_of(render_letter(BASE["pt"], BASE["name"], BASE["contact"]))
    assert "Prezado(a) Recrutador(a)" in text and "análise de crédito" in text


def test_a_valid_draft_passes():
    assert check_draft(draft(), BASE["en"], ALLOWED) is None


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"bullets": {"insight": ["made-up"], "credit": ["capacity"], "fapemat": ["models"], "support": ["repair"]}}, "unknown id"),
        ({"bullets": {"insight": [], "credit": ["capacity"], "fapemat": ["models"], "support": ["repair"]}}, "empty role"),
        ({"projects": ["secret-project"]}, "unknown id"),
        ({"skills": ["ai", "cooking"]}, "unknown id"),
        ({"summary": "AI engineer who cut costs by 47% at every job."}, "number"),
        ({"opening": "See my work at https://evil.example/cv"}, "link"),
        ({"match": "x" * 700}, "too long"),
    ],
)
def test_a_draft_with_an_unknown_id_a_new_number_or_a_foreign_link_is_refused(changes, reason):
    assert check_draft(draft(**changes), BASE["en"], ALLOWED) == reason
