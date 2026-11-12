"""The fact base split into passages, the unit the fact search ranks.

Responsibility: turn knowledge/facts.md into passages: each top-level bullet (with its wrapped lines) and each
paragraph is one, under its `## ` section; a nested bullet carries its parent's bold name ("Notes app: ..."); the
title and the intro before the first section are about the file, so they're skipped; Markdown bold and code marks
are dropped. Ids follow the file order, so the site's map and the API agree on which dot is which.
Public API: Passage, passages.
Used by: app.services.search.
Depends on: nothing.
Tests: tests/test_passages.py.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Passage:
    id: int
    section: str
    text: str


def _plain(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("**", "").replace("`", "")).strip()


def passages(md: str) -> list[Passage]:
    found: list[tuple[str, str]] = []
    section: str | None = None
    parent: str | None = None  # bold name of the bullet that owns the nested ones
    cur: list[str] = []

    def flush() -> None:
        if cur and section:
            found.append((section, _plain(" ".join(cur))))
        cur.clear()

    for line in md.splitlines():
        if line.startswith("## "):
            flush()
            section, parent = line[3:].strip(), None
        elif section is None:
            continue
        elif m := re.match(r"- (.*)", line):
            flush()
            bold = re.match(r"\*\*(.+?)\*\*", m[1])
            parent = bold[1].rstrip(".") if bold else None
            cur.append(m[1])
        elif m := re.match(r" {2}- (.*)", line):
            flush()
            cur.append(f"{parent}: {m[1]}" if parent else m[1])
        elif not line.strip():
            flush()
        else:
            cur.append(line.strip())
    flush()
    return [Passage(i, s, t) for i, (s, t) in enumerate(found)]
