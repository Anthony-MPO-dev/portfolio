"""Fact search: "Search what the bot knows" on the home page, run on the server (decision of 12/11).

Responsibility: index the passages of the fact base once (a vector each, from the injected embedder, a 2D map of
them by PCA, the keyword counts), leaving out the bot's own rules ("What the bot doesn't share"), then pick the 5
for a question: the vector ranking and a keyword ranking (BM25, only passages that share a word with the question)
fused by reciprocal rank, which keeps a rare name like "Kai" from losing to what merely sounds close. The 5 come back
in the order of the cosine similarity the page shows; the question gets its place on the same map.
SearchService adds what the route needs: the question trimmed and at most 200 characters, per-visitor limits (a
minute and a day) so the route isn't a free embedding API, and at most 2 searches at a time (a third waits 2 s, then
"busy"), so a burst can't take the CPU from the chat. The model runs one thread per search. Questions are never kept
or logged.
Public API: FactSearch (facts, search), SearchService (ask, facts), SearchLimits, Fact, Hit, Found, SearchAnswer,
HIDDEN_SECTIONS.
Used by: app.http (GET /api/search/facts, POST /api/search), app.main.
Depends on: numpy, app.search.passages, the store's hit_search counter.
Tests: tests/test_search.py; the real model on the search set: golden/search_eval.py.
"""

import math
import re
import threading
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np

from app.search.passages import Passage

Embed = Callable[[Sequence[str], Literal["query", "passage"]], list[list[float]]]
RRF_K = 60  # reciprocal rank fusion constant
HIDDEN_SECTIONS = {"What the bot doesn't share"}  # the bot's rules, not facts about Anthony


@dataclass(frozen=True)
class Fact:
    id: int
    section: str
    text: str
    xy: tuple[float, float]


@dataclass(frozen=True)
class Hit:
    id: int
    score: float  # cosine similarity between the question and the passage


@dataclass(frozen=True)
class Found:
    hits: list[Hit]
    xy: tuple[float, float]


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"\w+", text.lower()) if len(w) > 1]


class FactSearch:
    def __init__(self, passages: Sequence[Passage], embed: Embed, top: int = 5):
        self.passages = [p for p in passages if p.section not in HIDDEN_SECTIONS]
        self.embed, self.top = embed, top
        self.vectors = np.array(embed([f"{p.section}. {p.text}" for p in self.passages], "passage"))
        self.mean = self.vectors.mean(axis=0)
        _, _, components = np.linalg.svd(self.vectors - self.mean, full_matrices=False)
        self.axes = components[:2]  # the map: the two directions the passages spread along most
        docs = [_words(f"{p.section} {p.text}") for p in self.passages]
        self.counts = [(Counter(d), len(d)) for d in docs]
        self.avg_len = sum(n for _, n in self.counts) / len(docs)
        self.df = Counter(w for d in docs for w in set(d))
        self.map = [Fact(p.id, p.section, p.text, self._place(v)) for p, v in zip(self.passages, self.vectors)]

    def _place(self, vector: np.ndarray) -> tuple[float, float]:
        x, y = (vector - self.mean) @ self.axes.T
        return round(float(x), 5), round(float(y), 5)

    def facts(self) -> list[Fact]:
        return self.map

    def _bm25(self, query: list[str], k1: float = 1.2, b: float = 0.75) -> np.ndarray:
        n, scores = len(self.counts), np.zeros(len(self.counts))
        for i, (tf, length) in enumerate(self.counts):
            for w in query:
                if w in tf:
                    idf = math.log(1 + (n - self.df[w] + 0.5) / (self.df[w] + 0.5))
                    scores[i] += idf * tf[w] * (k1 + 1) / (tf[w] + k1 * (1 - b + b * length / self.avg_len))
        return scores

    def search(self, question: str) -> Found:
        vector = np.array(self.embed([question], "query")[0])
        cosine = self.vectors @ vector
        keyword = self._bm25(_words(question))
        rank = lambda s: np.argsort(np.argsort(-s))  # noqa: E731 - 0 is the best
        fused = 1 / (RRF_K + rank(cosine)) + np.where(keyword > 0, 1 / (RRF_K + rank(keyword)), 0)
        best = sorted(np.argsort(-fused)[: self.top], key=lambda i: -cosine[i])  # chosen by fusion, shown by similarity
        hits = [Hit(self.passages[i].id, round(float(cosine[i]), 4)) for i in best]
        return Found(hits, self._place(vector))


@dataclass(frozen=True)
class SearchLimits:
    max_chars: int = 200
    per_ip_minute: int = 20
    per_ip_day: int = 300
    parallel: int = 2  # searches at the same time
    wait: float = 2.0  # seconds a search waits for a slot before "busy"


@dataclass(frozen=True)
class SearchAnswer:
    status: Literal["ok", "invalid", "rate_limited", "busy"]
    found: Found | None = None


class SearchService:
    def __init__(self, search: FactSearch, store, limits: SearchLimits = SearchLimits()):
        self.search, self.store, self.limits = search, store, limits  # store: hit_search, as in app.ports.SessionStore
        self.slots = threading.BoundedSemaphore(limits.parallel)

    def facts(self) -> list[Fact]:
        return self.search.facts()

    def ask(self, *, client_key: str, question: str) -> SearchAnswer:
        question = question.strip()
        if not question or len(question) > self.limits.max_chars:
            return SearchAnswer("invalid")
        minute, day = self.store.hit_search(client_key)
        if minute > self.limits.per_ip_minute or day > self.limits.per_ip_day:
            return SearchAnswer("rate_limited")
        if not self.slots.acquire(timeout=self.limits.wait):
            return SearchAnswer("busy")
        try:
            return SearchAnswer("ok", self.search.search(question))
        finally:
            self.slots.release()
