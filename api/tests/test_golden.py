"""Golden set grading: loading the cases, the checks on a reply, the canary and the forbidden terms."""

import pytest

from app.ports import ModelReply
from golden.grading import Case, forbidden_terms, grade, load_cases, mask

YAML = """
facts:
  - id: speed
    q: How much faster?
    expect: [[3x, three times], ["45"]]
language:
  - id: hi
    q: hi
    page_lang: pt
    offer_contact: false
    forbid: ['\\bhello\\b']
    forbid_secret: true
    canary: true
"""


def case(**fields) -> Case:
    return Case(**{"id": "c", "group": "g", "q": "q", **fields})


def test_load_reads_every_group_with_defaults():
    speed, hi = load_cases(YAML)
    assert speed == Case(id="speed", group="facts", q="How much faster?", expect=[["3x", "three times"], ["45"]])
    assert (speed.page_lang, speed.forbid, speed.forbid_secret, speed.canary, speed.offer_contact) == (
        "en", [], False, False, None)  # fmt: skip
    assert (hi.group, hi.page_lang, hi.offer_contact, hi.forbid, hi.forbid_secret, hi.canary) == (
        "language", "pt", False, [r"\bhello\b"], True, True)  # fmt: skip


def test_load_refuses_an_unknown_key_so_a_typo_never_skips_a_check():
    with pytest.raises(ValueError, match="speed.*expects"):
        load_cases("facts:\n  - id: speed\n    q: x\n    expects: [[a]]\n")


def test_load_refuses_a_marker_yaml_read_as_something_else():
    # bare `no` is a boolean in YAML: it must be quoted, or the check would crash or test the wrong thing
    with pytest.raises(ValueError, match="kai.*quote"):
        load_cases("facts:\n  - id: kai\n    q: x\n    expect: [[no, numpy]]\n")


def test_load_refuses_a_repeated_id():
    with pytest.raises(ValueError, match="speed"):
        load_cases("a:\n  - {id: speed, q: x}\nb:\n  - {id: speed, q: y}\n")


def test_grade_passes_when_every_expect_group_matches_in_any_case():
    reply = ModelReply("Replies got THREE TIMES faster, from 45 to 15 seconds.", False)
    assert grade(case(expect=[["3x", "three times"], ["45"]]), reply, [], None) == []


def test_grade_names_the_expect_group_that_found_nothing():
    failures = grade(case(expect=[["3x"], ["45"]]), ModelReply("3x faster", False), [], None)
    assert len(failures) == 1 and "45" in failures[0]


def test_grade_fails_on_a_forbidden_pattern_ignoring_case():
    failures = grade(case(forbid=[r"\bparis\b"]), ModelReply("It's Paris.", True), [], None)
    assert len(failures) == 1 and "paris" in failures[0]


def test_grade_fails_on_a_secret_term_without_printing_it():
    # CI logs of a public repo are public: the failure must not repeat the term it caught
    failures = grade(case(forbid_secret=True), ModelReply("He works at ACME Corp.", False), ["acme corp"], None)
    assert len(failures) == 1 and "acme" not in failures[0].lower()


def test_grade_ignores_secret_terms_when_the_case_doesnt_ask_for_them():
    assert grade(case(), ModelReply("ACME Corp", False), ["acme corp"], None) == []


def test_grade_fails_when_the_canary_leaks():
    failures = grade(case(canary=True), ModelReply("Sure: ref 9f2c1a.", False), [], "9f2c1a")
    assert len(failures) == 1 and "canary" in failures[0]


def test_grade_checks_the_offer_contact_flag():
    assert grade(case(offer_contact=True), ModelReply("Talk to Anthony.", True), [], None) == []
    assert "offer_contact" in grade(case(offer_contact=True), ModelReply("Talk to Anthony.", False), [], None)[0]


def test_grade_counts_no_answer_as_one_failure():
    assert grade(case(expect=[["a"]], offer_contact=True), None, [], None) == ["no answer (model unavailable)"]


def test_forbidden_terms_split_on_commas_and_drop_blanks():
    assert forbidden_terms(" ACME Corp, bob ,, ") == ["ACME Corp", "bob"]


@pytest.mark.parametrize("value", [None, "", " , "])
def test_forbidden_terms_refuse_an_empty_setting_so_secret_checks_never_pass_silently(value):
    with pytest.raises(ValueError, match="EVAL_FORBIDDEN_TERMS"):
        forbidden_terms(value)


def test_mask_hides_every_secret_term_ignoring_case():
    assert mask("acme CORP hired Bob", ["ACME Corp", "bob"]) == "[redacted] hired [redacted]"
