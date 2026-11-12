from pathlib import Path

from app.search.passages import Passage, passages

MD = """# Jane Doe: public facts

Single source of truth. This intro is about the file, not about Jane.

## At a glance

- AI engineer. She makes **agents** work,
  and she measures it.
- Based in Brazil.

## Side projects

- **Notes app.** FastAPI and `ChromaDB`.
  - Chunks of 1,000 characters.
  - A bug she fixed: the index was wiped
    on every restart.
- **Kai.** No ChromaDB.

A paragraph after the list,
on two lines.
"""


def test_each_bullet_and_paragraph_becomes_a_passage_under_its_section():
    ps = passages(MD)
    assert [(p.section, p.text) for p in ps] == [
        ("At a glance", "AI engineer. She makes agents work, and she measures it."),
        ("At a glance", "Based in Brazil."),
        ("Side projects", "Notes app. FastAPI and ChromaDB."),
        ("Side projects", "Notes app: Chunks of 1,000 characters."),
        ("Side projects", "Notes app: A bug she fixed: the index was wiped on every restart."),
        ("Side projects", "Kai. No ChromaDB."),
        ("Side projects", "A paragraph after the list, on two lines."),
    ]


def test_ids_follow_the_file_order_so_the_site_and_the_api_agree():
    assert [p.id for p in passages(MD)] == list(range(7))


def test_the_title_and_the_intro_before_the_first_section_are_skipped():
    texts = " ".join(p.text for p in passages(MD))
    assert "public facts" not in texts and "Single source" not in texts


def test_a_file_without_sections_has_no_passages():
    assert passages("# Title\n\nJust an intro.\n") == []


def test_the_real_fact_base_names_anthony_in_a_passage_of_its_own():
    facts = (Path(__file__).resolve().parents[2] / "knowledge" / "facts.md").read_text(encoding="utf-8")
    ps = passages(facts)
    assert Passage(0, "At a glance", "Name: Anthony Muniz.") == ps[0]
    assert len(ps) > 50
