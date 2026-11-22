import subprocess

import pytest

from golden.leak_scan import find, main, pushed, texts


def test_a_planted_term_is_found_in_any_case_with_its_file_and_line():
    files = [("knowledge/facts.md", "Anthony builds agents.\nHe worked for ACME Corp in 2024.\n"), ("site/a.ts", "ok")]
    assert find(files, ["acme corp"]) == [("knowledge/facts.md", 2)]


def test_a_term_wrapped_across_lines_or_with_two_spaces_is_found_at_the_line_it_starts():
    files = [("a.md", "x\nHe worked for ACME\ncorp in 2024.\n"), ("b.md", "ok\nacme  corp"), ("c.md", "acmecorp")]
    assert find(files, ["acme corp"]) == [("a.md", 2), ("b.md", 2)]


def test_a_line_with_two_hits_is_reported_once():
    assert find([("a.md", "acme corp and ACME\tCORP")], ["acme corp"]) == [("a.md", 1)]


def test_a_number_counts_only_on_its_own_not_inside_a_hash_or_a_longer_number():
    lock = 'hash = "sha256:05cd2cd39055d0b912346e4513ef"\nsize = 123456\n'
    assert find([("uv.lock", lock)], ["1234"]) == []
    assert find([("facts.md", "paid 1234 a month\nR$1234,00")], ["1234"]) == [("facts.md", 1), ("facts.md", 2)]


def test_a_clean_repo_has_no_hits():
    assert find([("knowledge/facts.md", "Anthony builds agents.")], ["acme corp", "salary 9000"]) == []


def test_the_report_names_the_file_and_line_but_never_the_term(capsys):
    code = main("Acme Corp, other", [("knowledge/facts.md", "x\nacme corp here\n")])
    out = capsys.readouterr().out
    assert code == 1
    assert "knowledge/facts.md:2" in out
    assert "acme" not in out.lower() and "other" not in out


def test_no_terms_is_an_error_so_the_check_never_passes_silently(capsys):
    assert main("", [("a.md", "anything")]) == 2
    assert main(" , ", [("a.md", "anything")]) == 2


def test_a_clean_scan_passes_and_says_how_much_it_read(capsys):
    assert main("acme corp", [("a.md", "fine"), ("b.ts", "also fine")]) == 0
    assert "2 files" in capsys.readouterr().out


def test_texts_reads_the_tracked_text_files_and_skips_binaries(tmp_path):
    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q")
    (tmp_path / "facts.md").write_text("hello", encoding="utf-8")
    (tmp_path / "photo.webp").write_bytes(b"RIFF\x00\x01\xff\xfe")
    (tmp_path / "untracked.md").write_text("not in git", encoding="utf-8")
    git("add", "facts.md", "photo.webp")
    assert dict(texts(tmp_path)) == {"facts.md": "hello"}


def test_a_hit_in_the_pushed_commits_names_only_the_commit(capsys):
    commits = [("abc1234", "Add facts\n\nnothing here"), ("def5678", "Fix\n\nworked at acme\ncorp")]
    code = main("Acme Corp", [("a.md", "clean")], commits)
    out = capsys.readouterr().out
    assert code == 1
    assert "commit def5678" in out and "abc1234" not in out and "def5678:" not in out
    assert "acme" not in out.lower() and "worked" not in out
    assert "1 files, 2 commits" in out


def git(root, *args) -> str:
    who = ["-c", "user.name=t", "-c", "user.email=t@t"]
    return subprocess.run(["git", *who, *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


def commit(root, message, **files) -> str:
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "--allow-empty", "-m", message)
    return git(root, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q", "-b", "main")
    commit(tmp_path, "first", facts="old line\n")
    return tmp_path


def test_pushed_reads_each_commit_message_and_only_the_lines_it_added(repo):
    base = git(repo, "rev-parse", "HEAD")
    a = commit(repo, "planted in the message: acme", facts="old line\nhe worked at\nacme corp\n")
    b = commit(repo, "take it out", facts="old line\n")
    got = dict(pushed(base, b, "main", repo))
    assert list(got) == [a[:7], b[:7]]
    assert "planted in the message: acme" in got[a[:7]] and "he worked at\nacme corp" in got[a[:7]]
    assert "old line" not in got[a[:7]] + got[b[:7]]  # unchanged and removed lines aren't part of the push
    # the term already left the tip: only the history scan still sees it
    assert [sha for sha, _ in find(got.items(), ["acme corp"])] == [a[:7]]


@pytest.mark.parametrize("before", ["0" * 40, "1" * 40])  # a new branch; a force push whose old tip wasn't fetched
def test_pushed_starts_from_the_default_branch_when_the_old_tip_is_unknown(repo, before):
    git(repo, "checkout", "-q", "-b", "feature")
    a = commit(repo, "feature work")
    assert [sha for sha, _ in pushed(before, a, "main", repo)] == [a[:7]]


@pytest.mark.parametrize("value", ["acme corp", "ACME CORP\n"])
def test_terms_come_from_the_same_comma_list_as_the_golden_set(value, capsys):
    assert main(value, [("a.md", "Acme Corp")]) == 1


def test_a_force_push_on_the_default_branch_rescans_its_whole_history(repo):
    first = git(repo, "rev-parse", "HEAD")
    a = commit(repo, "second")
    # the old tip is gone and the default branch is the pushed head itself: every commit is read
    assert [sha for sha, _ in pushed("1" * 40, a, "main", repo)] == [first[:7], a[:7]]
