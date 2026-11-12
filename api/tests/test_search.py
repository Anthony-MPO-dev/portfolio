"""Fact search: every passage on the map, the closest ones for a question (meaning plus a keyword score), the
question's place on the map, and the limits that keep it from being a free embedding API."""

import math

from app.search.passages import Passage
from app.services.search import FactSearch, SearchLimits, SearchService
from tests.fakes import FakeStore

PASSAGES = [
    Passage(0, "At a glance", "Name: Anthony Muniz."),
    Passage(1, "Credit fund", "Credit analysis used to take about an hour."),
    Passage(2, "RAG", "Resume generator on ChromaDB, one collection per user."),
    Passage(3, "RAG", "Kai, a personal copilot. Doesn't use ChromaDB."),
    Passage(4, "LogStream", "His first Go project, with gRPC."),
    Passage(5, "What the bot doesn't share", "Salary, compensation or hourly rates."),
]
AXES = ["name", "credit", "chromadb", "kai", "go"]


def fake_embed(texts, kind):
    """A vector per text: how often each axis word shows up (plus a little of everything), normalized. Like the real
    model, "chromadb" pulls both RAG passages together, and "kai" alone is a weak signal."""
    out = []
    for text in texts:
        words = text.lower().replace(".", " ").replace("?", " ").replace(",", " ").split()
        v = [0.1 + sum(w == axis for w in words) * (0.3 if axis == "kai" else 1.0) for axis in AXES]
        n = math.sqrt(sum(x * x for x in v))
        out.append([x / n for x in v])
    return out


def make(limits=SearchLimits()):
    store = FakeStore()
    return SearchService(FactSearch(PASSAGES, fake_embed), store, limits), store


def test_every_passage_is_on_the_map_with_its_place():
    facts = FactSearch(PASSAGES, fake_embed).facts()
    assert [(f.id, f.section, f.text) for f in facts] == [(p.id, p.section, p.text) for p in PASSAGES[:5]]
    assert all(len(f.xy) == 2 and all(math.isfinite(c) for c in f.xy) for f in facts)


def test_the_closest_passage_comes_first_with_its_similarity():
    found = FactSearch(PASSAGES, fake_embed).search("How long did the credit analysis take?")
    assert found.hits[0].id == 1
    assert -1 <= found.hits[-1].score <= found.hits[0].score <= 1


def test_a_rare_word_of_the_question_brings_its_passage_up():
    # by meaning alone the ChromaDB passages win; "Kai" in the text puts Kai's passage first
    found = FactSearch(PASSAGES, fake_embed).search("Does Kai use ChromaDB?")
    assert found.hits[0].id == 3


def test_at_most_five_hits_and_the_question_lands_where_its_twin_passage_is():
    search = FactSearch(PASSAGES[:4] + PASSAGES[4:] * 1, fake_embed, top=3)
    found = search.search("His first Go project, with gRPC.")
    assert len(found.hits) == 3
    twin = next(f for f in search.facts() if f.id == 4)
    assert all(abs(a - b) < 1e-6 for a, b in zip(found.xy, twin.xy))


def test_the_service_answers_and_says_nothing_is_kept():
    service, _ = make()
    answer = service.ask(client_key="ip-a", question="  Does Kai use ChromaDB?  ")
    assert answer.status == "ok" and answer.found.hits[0].id == 3


def test_an_empty_or_too_long_question_is_invalid_and_costs_nothing():
    service, store = make(SearchLimits(max_chars=20, per_ip_minute=1))
    assert service.ask(client_key="ip-a", question="   ").status == "invalid"
    assert service.ask(client_key="ip-a", question="x" * 21).status == "invalid"
    assert service.ask(client_key="ip-a", question="credit?").status == "ok"


def test_each_visitor_has_a_minute_and_a_day_limit():
    service, _ = make(SearchLimits(per_ip_minute=2, per_ip_day=100))
    assert [service.ask(client_key="ip-a", question="go?").status for _ in range(3)] == ["ok", "ok", "rate_limited"]
    assert service.ask(client_key="ip-b", question="go?").status == "ok"
    service, _ = make(SearchLimits(per_ip_minute=100, per_ip_day=1))
    assert [service.ask(client_key="ip-a", question="go?").status for _ in range(2)] == ["ok", "rate_limited"]


def test_the_bot_s_own_rules_are_not_facts_on_the_map():
    facts = FactSearch(PASSAGES, fake_embed).facts()
    assert all(f.section != "What the bot doesn't share" for f in facts) and len(facts) == 5


def test_the_hits_come_in_the_order_of_the_similarity_they_show():
    found = FactSearch(PASSAGES, fake_embed).search("Does Kai use ChromaDB?")
    scores = [h.score for h in found.hits]
    assert scores == sorted(scores, reverse=True)


def test_too_many_searches_at_once_are_turned_away_so_the_chat_keeps_its_cpu():
    service, _ = make(SearchLimits(parallel=1, wait=0))
    service.slots.acquire()  # one search already running
    assert service.ask(client_key="ip-a", question="go?").status == "busy"
    service.slots.release()
    assert service.ask(client_key="ip-a", question="go?").status == "ok"
