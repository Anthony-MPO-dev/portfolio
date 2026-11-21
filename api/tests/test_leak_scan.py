import subprocess

import pytest

from golden.leak_scan import find, main, texts


def test_a_planted_term_is_found_in_any_case_with_its_file_and_line():
    files = [("knowledge/facts.md", "Anthony builds agents.\nHe worked for ACME Corp in 2024.\n"), ("site/a.ts", "ok")]
    assert find(files, ["acme corp"]) == [("knowledge/facts.md", 2)]


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


@pytest.mark.parametrize("value", ["acme corp", "ACME CORP\n"])
def test_terms_come_from_the_same_comma_list_as_the_golden_set(value, capsys):
    assert main(value, [("a.md", "Acme Corp")]) == 1
