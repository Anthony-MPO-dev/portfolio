"""Secret leak scan: no secret term from EVAL_FORBIDDEN_TERMS appears in any file the public repo tracks, nor in a
commit the push (or pull request) adds.

Responsibility: read every tracked text file (git ls-files; binaries are skipped) and, given the pushed range, each new
commit's message and added lines (git log -p from the push's old tip, or the pull request's base, to its head; a new
branch, or a force push whose old tip the clone doesn't have, starts from the default branch). Look for each secret
term in any case, its words split by any run of whitespace (so a term wrapped across two lines still counts); a term
of digits only counts on its own, not inside a hash or a longer number: a lockfile's sha256 is full of them. Report a
file hit as "path:line" (where the match starts) and a history hit as "commit <short sha>" only: the log of a public
repo's CI is public, so a hit never prints the term or its line. A term in history stays public until the branch is
rewritten, so that red run is the signal. The terms are the golden set's (same comma-separated list,
golden.grading.forbidden_terms); none is an error, so the check never passes silently. Exit 0 clean, 1 on a hit, 2
without terms. The CI runs it on every push (.github/workflows/ci.yml, with SCAN_BASE, SCAN_HEAD and SCAN_DEFAULT
naming the range); a planted term turns it red.
Run: uv run python -m golden.leak_scan (from api/, with EVAL_FORBIDDEN_TERMS set; without SCAN_HEAD, files only).
Public API: find, texts, pushed, main.
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


def _pattern(term: str) -> str:
    words = r"\s+".join(map(re.escape, term.split()))
    return rf"(?<![0-9a-z]){words}(?![0-9a-z])" if term.isdigit() else words


def find(files: Iterable[tuple[str, str]], terms: list[str]) -> list[tuple[str, int]]:
    pattern = re.compile("|".join(map(_pattern, terms)), re.IGNORECASE)
    hits = ((path, text.count("\n", 0, m.start()) + 1) for path, text in files for m in pattern.finditer(text))
    return list(dict.fromkeys(hits))  # one per line


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", *args], cwd=root, check=check, capture_output=True)


def texts(root: Path = REPO) -> Iterator[tuple[str, str]]:
    for path in filter(None, _git(root, "ls-files", "-z").stdout.decode().split("\0")):
        try:
            text = (root / path).read_bytes().decode("utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # a binary (image, model) or a file deleted in the working tree
        if "\0" not in text:
            yield path, text


def _added(patch: str) -> Iterator[str]:
    hunk = False
    for line in patch.splitlines():
        if line.startswith("diff "):
            hunk = False
        elif line.startswith("@@"):
            hunk = True
        elif hunk and line.startswith("+"):
            yield line[1:]


def pushed(base: str, head: str, default: str, root: Path = REPO) -> Iterator[tuple[str, str]]:
    known = base.strip("0") and _git(root, "cat-file", "-e", f"{base}^{{commit}}", check=False).returncode == 0
    log = _git(root, "log", "--reverse", "-p", "--unified=0", "--no-color", "--no-ext-diff", "--no-textconv",
               "--diff-merges=first-parent", "--format=%x00%H%x00%B%x00", f"{base if known else default}..{head}")
    parts = log.stdout.decode("utf-8", "replace").split("\0")[1:]
    for sha, message, patch in zip(parts[::3], parts[1::3], parts[2::3]):
        yield sha[:7], message + "\n" + "\n".join(_added(patch))


def main(value: str | None, files: Iterable[tuple[str, str]], commits: Iterable[tuple[str, str]] = ()) -> int:
    try:
        terms = forbidden_terms(value)
    except ValueError as error:
        print(error)
        return 2
    files, commits = list(files), list(commits)
    hits = find(files, terms)
    for path, n in hits:
        print(f"secret term at {path}:{n}")
    bad = list(dict.fromkeys(sha for sha, _ in find(commits, terms)))
    for sha in bad:
        print(f"secret term in commit {sha}")
    print(f"{len(files)} files, {len(commits)} commits, {len(terms)} terms, {len(hits) + len(bad)} hits")
    return 1 if hits or bad else 0


if __name__ == "__main__":
    env = os.environ
    commits = pushed(env.get("SCAN_BASE", ""), env["SCAN_HEAD"], env["SCAN_DEFAULT"]) if env.get("SCAN_HEAD") else ()
    sys.exit(main(env.get("EVAL_FORBIDDEN_TERMS"), texts(), commits))
