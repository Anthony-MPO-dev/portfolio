"""Secret leak scan: no secret term from EVAL_FORBIDDEN_TERMS appears in any file the public repo tracks.

Responsibility: read every tracked text file (git ls-files; binaries are skipped), look for each secret term in any
case (a term of digits only counts on its own, not inside a hash or a longer number: a lockfile's sha256 is full of
them), and report each hit as "path:line" only: the log of a public repo's CI is public, so a hit never prints the term
or its line. The terms are the golden set's (same comma-separated list, golden.grading.forbidden_terms); none is an
error, so the check never passes silently. Exit 0 clean, 1 on a hit, 2 without terms. The CI runs it on every push
(.github/workflows/ci.yml); a planted term turns it red.
Run: uv run python -m golden.leak_scan (from api/, with EVAL_FORBIDDEN_TERMS set).
Public API: find, texts, main.
Used by: the CI.
Depends on: golden.grading, git.
Tests: tests/test_leak_scan.py.
"""

import os
import re
import subprocess
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path

from golden.grading import forbidden_terms

REPO = Path(__file__).resolve().parents[2]


def find(files: Iterable[tuple[str, str]], terms: list[str]) -> list[tuple[str, int]]:
    pattern = re.compile(
        "|".join(rf"(?<![0-9a-z]){re.escape(t)}(?![0-9a-z])" if t.isdigit() else re.escape(t) for t in terms),
        re.IGNORECASE,
    )
    return [(path, n) for path, text in files for n, line in enumerate(text.splitlines(), 1) if pattern.search(line)]


def texts(root: Path = REPO) -> Iterator[tuple[str, str]]:
    listed = subprocess.run(["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True).stdout
    for path in filter(None, listed.decode().split("\0")):
        try:
            text = (root / path).read_bytes().decode("utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # a binary (image, model) or a file deleted in the working tree
        if "\0" not in text:
            yield path, text


def main(value: str | None, files: Iterable[tuple[str, str]]) -> int:
    try:
        terms = forbidden_terms(value)
    except ValueError as error:
        print(error)
        return 2
    files = list(files)
    hits = find(files, terms)
    for path, n in hits:
        print(f"secret term at {path}:{n}")
    print(f"{len(files)} files, {len(terms)} terms, {len(hits)} hits")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main(os.environ.get("EVAL_FORBIDDEN_TERMS"), texts()))
