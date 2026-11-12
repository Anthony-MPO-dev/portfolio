"""Search set, live: how often the fact search that runs on the site puts a right passage in its top 3, per language.

Responsibility: run every question of evals/search_set.yaml through app.services.search.FactSearch with the real model
(api/.models/multilingual-e5-small, the files the API image downloads; out of git) and print hit@1, hit@3 and the mean
reciprocal rank per language, on the 5 the page shows in the order it shows them (a right passage left out counts
as rank 6), with the misses and the time per question. It's how the model and the keyword fusion were
chosen (12/11: 27 of 30 in the top 3), and how a change to either is checked.
Run from api/: uv run python -m golden.search_eval
Public API: none (script).
Used by: Anthony's PC (dev only, not in the API image).
Depends on: app.search.passages, app.services.search, app.adapters.onnx_embedder, numpy, pyyaml.
Tests: this is the check.
"""

import time
from pathlib import Path

import numpy as np
import yaml

from app.adapters.onnx_embedder import E5_PREFIXES, OnnxEmbedder
from app.search.passages import passages
from app.services.search import FactSearch

ROOT = Path(__file__).resolve().parents[2]
MODEL = Path(__file__).resolve().parents[1] / ".models" / "multilingual-e5-small"


def main() -> None:
    ps = passages((ROOT / "knowledge" / "facts.md").read_text(encoding="utf-8"))
    cases = yaml.safe_load((ROOT / "evals" / "search_set.yaml").read_text(encoding="utf-8"))
    search = FactSearch(ps, OnnxEmbedder(MODEL, E5_PREFIXES).embed)  # the 5 the page shows, in its order
    stats: dict[str, list[int]] = {}
    misses, t0 = [], time.perf_counter()
    for c in cases:
        pieces = [c["expect"]] if isinstance(c["expect"], str) else c["expect"]
        want = {p.id for piece in pieces for p in ps if piece.lower() in p.text.lower()}
        assert len(want) == len(pieces), f"{pieces} must each match one passage"
        order = [h.id for h in search.search(c["q"]).hits]
        rank = min((order.index(i) for i in want if i in order), default=len(order))  # 5: not shown at all
        stats.setdefault(c["lang"], []).append(rank)
        if rank >= 3:
            misses.append(f"{c['lang']} {c['q']} ({'not in the 5' if rank >= len(order) else f'rank {rank + 1}'})")
    ms = (time.perf_counter() - t0) * 1000 / len(cases)
    print(f"{len(ps)} passages, {len(cases)} questions, {ms:.0f} ms a question")
    for lang, rs in stats.items():
        print(f"  {lang}: @1 {sum(r == 0 for r in rs)}/{len(rs)}  @3 {sum(r < 3 for r in rs)}/{len(rs)}  "
              f"mrr {np.mean([1 / (r + 1) for r in rs]):.2f}")  # fmt: skip
    for m in misses:
        print("  miss:", m)


if __name__ == "__main__":
    main()
