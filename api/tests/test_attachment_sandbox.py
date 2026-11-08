"""Attachment sandbox: the conversion runs in a child process with no environment, a time limit and, on Linux, no
network, no programs, no file writes and 512 MB of memory. The Linux-only tests run in the API image (see ESTADO)."""

import io
import subprocess
import sys

import pytest
from PIL import Image

from app import attachment_sandbox
from app.attachment_sandbox import convert_isolated
from app.ports import AttachmentRejected

linux = pytest.mark.skipif(sys.platform != "linux", reason="seccomp and rlimits exist only on Linux (production)")


def png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (30, 20), (0, 0, 200)).save(out, "PNG")
    return out.getvalue()


def test_a_file_is_converted_in_the_child_and_comes_back_whole():
    result = convert_isolated(png())
    assert (result.kind, result.summary, Image.open(io.BytesIO(result.png)).size) == ("image", "image, 30x20", (30, 20))


def test_a_refused_file_keeps_its_reason():
    with pytest.raises(AttachmentRejected, match="type"):
        convert_isolated(b"MZ\x90\x00 an executable")


def test_a_conversion_leaves_nothing_where_the_child_ran():
    # Without SYSTEMDRIVE, Windows wrote "%SystemDrive%/ProgramData/..." caches into api/ and they reached a commit.
    convert_isolated(png())
    assert not list(attachment_sandbox.ROOT.glob("%*"))


def child(monkeypatch, code: str):
    monkeypatch.setattr(attachment_sandbox, "CHILD", [sys.executable, "-c", code])


def test_the_child_gets_no_secrets_from_the_api_environment(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://default:secret@redis:6379/0")
    child(monkeypatch, 'import os, json; print(json.dumps({"ok": False, "reason": "type" if "REDIS_URL" in os.environ else "no_text"}))')
    with pytest.raises(AttachmentRejected, match="no_text"):
        convert_isolated(png())


@pytest.mark.parametrize(
    "out",
    [
        {"ok": True, "kind": "image", "summary": "REDIS_URL=redis://default:secret@redis", "png": None},
        {"ok": True, "kind": "script", "summary": "pdf, 1 page", "text": "x"},
        {"ok": True, "kind": "pdf", "summary": "image, 2x2", "text": "x"},  # summary and kind disagree
        {"ok": True, "kind": "image", "summary": "image, 2x2", "png": "bm90IGEgcG5n"},  # not a PNG
        {"ok": True, "kind": "image", "summary": "image, 2x2", "text": "secret", "png": "iVBORw0KGgo="},
        {"ok": True, "kind": "pdf", "summary": "pdf, 1 page", "text": "x" * 30_001},
        {"ok": False, "reason": "WORKER_TOKEN=abc"},
    ],
)
def test_the_parent_takes_nothing_from_the_child_beyond_the_expected_shape(monkeypatch, out):
    import json

    child(monkeypatch, f"print({json.dumps(out)!r})")
    with pytest.raises(AttachmentRejected, match="^unreadable$"):
        convert_isolated(png())


def test_a_child_that_hangs_is_stopped(monkeypatch):
    child(monkeypatch, "import time; time.sleep(30)")
    with pytest.raises(AttachmentRejected, match="too_big"):
        convert_isolated(png(), timeout=1)


@pytest.mark.parametrize("code", ["import sys; sys.exit(3)", "print('not json')"])
def test_a_child_that_crashes_or_talks_nonsense_is_a_refusal(monkeypatch, code):
    child(monkeypatch, code)
    with pytest.raises(AttachmentRejected, match="unreadable"):
        convert_isolated(png())


def locked(code: str) -> subprocess.CompletedProcess:
    script = f"from app.attachment_sandbox import lock_down; lock_down()\n{code}"
    return subprocess.run([sys.executable, "-B", "-c", script], capture_output=True, text=True, timeout=30)


@linux
@pytest.mark.parametrize(
    "attempt",
    [
        "import socket; socket.socket()",  # no network, not even to Redis or Postgres next door
        "import os; os.execv('/bin/sh', ['sh', '-c', 'true'])",  # no programs
        "import subprocess; subprocess.run(['true'])",
    ],
)
def test_locked_child_can_not_open_a_socket_or_run_a_program(attempt):
    run = locked(attempt)
    assert run.returncode != 0 and "PermissionError" in run.stderr


@linux
def test_locked_child_can_not_write_a_file():
    probe = "/tmp/attachment-sandbox-probe"
    run = locked(f"with open('{probe}', 'w') as f:\n    f.write('x' * 10)")
    assert run.returncode != 0 and "File too large" in run.stderr  # Python ignores SIGXFSZ, so it's an error
    assert open(probe).read() == ""  # created empty at most: not a byte written


@linux
def test_locked_child_can_not_read_the_api_process_environment_or_memory():
    # The API process holds DATABASE_URL and WORKER_TOKEN; a parser exploit in the child must not reach them.
    run = locked("import os\nfor f in ('environ', 'mem'):\n    try:\n        open(f'/proc/{os.getppid()}/{f}', 'rb').read(1)\n"
                 "        print('read', f)\n    except OSError as e:\n        print('denied', f, e.errno)")  # fmt: skip
    assert "read" not in run.stdout and run.stdout.count("denied") == 2


@linux
def test_locked_child_can_not_take_more_than_512_mb():
    run = locked("x = bytearray(700 * 1024 * 1024)")
    assert run.returncode != 0 and "MemoryError" in run.stderr


def test_conversions_beyond_the_slots_wait_briefly_then_are_refused_as_busy(monkeypatch):
    import threading

    monkeypatch.setattr(attachment_sandbox, "SLOTS", threading.BoundedSemaphore(1))
    monkeypatch.setattr(attachment_sandbox, "SLOT_WAIT", 0.1)
    attachment_sandbox.SLOTS.acquire()  # another visitor's file is being converted
    with pytest.raises(AttachmentRejected, match="busy"):
        convert_isolated(png())
    attachment_sandbox.SLOTS.release()
    assert convert_isolated(png()).kind == "image"
