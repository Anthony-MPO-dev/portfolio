"""Search set, live: which model (and whether a keyword score on top) finds the right passage, per language.

Responsibility: run every question of evals/search_set.yaml through each candidate on the real models in
api/.models/ (downloaded by hand, out of git) and print hit@1, hit@3 and the mean reciprocal rank per language,
plus the time per question. It's how the fact search's model was chosen, and how a change to it is checked.
Run from api/: uv run python -m golden.search_eval
Public API: none (script).
Used by: Anthony's PC (dev only, not in the API image).
Depends on: app.search.passages, app.adapters.onnx_embedder, numpy, pyyaml.
Tests: this is the check.
"""

import math
import re
import time
from collections import Counter
from pathlib import Path

import numpy as np
import yaml

from app.adapters.onnx_embedder import OnnxEmbedder
from app.search.passages import passages

ROOT = Path(__file__).resolve().parents[2]
MODELS = Path(__file__).resolve().parents[1] / ".models"
CANDIDATES = {
    "multilingual-e5-small": {"query": "query: ", "passage": "passage: "},
    "paraphrase-multilingual-MiniLM-L12-v2": {},
}


def words(s: str) -> list[str]:
    return [w for w in re.findall(r"\w+", s.lower()) if len(w) > 1]


def bm25(docs: list[list[str]], q: list[str], k1: float = 1.2, b: float = 0.75) -> np.ndarray:
    n, avg = len(docs), sum(map(len, docs)) / len(docs)
    df = Counter(w for d in docs for w in set(d))
    out = np.zeros(n)
    for i, d in enumerate(docs):
        tf = Counter(d)
        for w in q:
            if w in tf:
                idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
                out[i] += idf * tf[w] * (k1 + 1) / (tf[w] + k1 * (1 - b + b * len(d) / avg))
    return out


def ranks(scores: np.ndarray) -> np.ndarray:
    r = np.empty(len(scores), dtype=int)
    r[np.argsort(-scores)] = np.arange(len(scores))
    return r


def main() -> None:
    ps = passages((ROOT / "knowledge" / "facts.md").read_text(encoding="utf-8"))
    cases = yaml.safe_load((ROOT / "evals" / "search_set.yaml").read_text(encoding="utf-8"))
    want = []
    for c in cases:
        pieces = [c["expect"]] if isinstance(c["expect"], str) else c["expect"]
        ids = set()
        for piece in pieces:
            hit = [p.id for p in ps if piece.lower() in p.text.lower()]
            assert len(hit) == 1, f"{piece!r} matches {len(hit)} passages"
            ids.add(hit[0])
        want.append(ids)
    docs = [words(f"{p.section} {p.text}") for p in ps]
    print(f"{len(ps)} passages, {len(cases)} questions\n")
    for name, prefixes in CANDIDATES.items():
        emb = OnnxEmbedder(MODELS / name, prefixes)
        pv = np.array(emb.embed([f"{p.section}. {p.text}" for p in ps], "passage"))
        t0 = time.perf_counter()
        qv = np.array([emb.embed([c["q"]], "query")[0] for c in cases])
        ms = (time.perf_counter() - t0) * 1000 / len(cases)
        dense = qv @ pv.T
        for mode in ("dense", "hybrid"):
            stats: dict[str, list[float]] = {}
            misses = []
            for i, c in enumerate(cases):
                s = dense[i]
                if mode == "hybrid":  # reciprocal rank fusion; only passages that share a word get a keyword rank
                    kw = bm25(docs, words(c["q"]))
                    s = 1 / (60 + ranks(s)) + np.where(kw > 0, 1 / (60 + ranks(kw)), 0)
                r = int(min(ranks(s)[j] for j in want[i]))
                stats.setdefault(c["lang"], []).append(r)
                if r >= 3:
                    misses.append(f"{c['lang']} {c['q']} (rank {r + 1})")
            line = "  ".join(
                f"{lang}: @1 {sum(r == 0 for r in rs)}/{len(rs)} @3 {sum(r < 3 for r in rs)}/{len(rs)} "
                f"mrr {np.mean([1 / (r + 1) for r in rs]):.2f}"
                for lang, rs in stats.items()
            )
            print(f"{name} {mode} ({ms:.0f} ms/question)\n  {line}")
            for m in misses:
                print("   miss:", m)
        print()


if __name__ == "__main__":
    main()
