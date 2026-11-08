"""Attachment sandbox: converts a visitor's file in a child process that can't reach anything.

Responsibility: the security research (section 4) asks for the conversion in a separate container with no network,
no root, 512 MB and 20 s per file. An Easypanel app can't run with --network none and still be reachable, and handing
the API the Docker socket would be worse, so the same limits are applied to a child process instead:
- the file goes in through stdin and the result comes back through stdout: nothing is written to disk, and the
  original only ever lives in memory;
- the child starts with an empty environment (no Redis, Postgres or webhook secrets) and writes no bytecode;
- on Linux (production) it locks itself down before reading a byte: 512 MB of address space, 20 s of CPU, no file
  writes (RLIMIT_FSIZE 0), and a seccomp filter that refuses socket, socketpair, execve and execveat, so a parser
  exploit can neither reach the network next door nor start a program. The API runs as a non-root user already;
- the parent waits at most 20 s; a hang, a crash or nonsense output is a refusal, and it takes back only the shape
  a conversion can have (a known kind, a summary the converter writes, a real PNG, text within the limit), so a
  hijacked child can't hand the visitor anything else;
- the API process can't be read by its children (not dumpable), and a locked child can't be read by its siblings or
  trace anyone: the secrets in the API's environment and another visitor's file stay out of reach;
- at most 3 children run at once (512 MB each on a shared VPS); a file that finds no slot within 10 s is refused as
  "busy". A visitor's files arrive as separate requests, so they convert side by side (standards item 15).
Public API: convert_isolated, lock_down, not_dumpable, CHILD.
Used by: app.main (the chat use case's attachment converter).
Depends on: app.attachments (run in the child), app.ports, pyseccomp, resource and ctypes (Linux only).
Tests: tests/test_attachment_sandbox.py (the lock-down tests run on Linux, in the API image).
"""

import base64
import binascii
import errno
import json
import os
import re
import subprocess
import sys
import threading
from pathlib import Path

from app.attachments import TEXT_MAX, convert
from app.ports import Attachment, AttachmentRejected

TIMEOUT = 20  # seconds, wall clock in the parent and CPU in the child
MEMORY = 512 * 1024 * 1024
ROOT = Path(__file__).resolve().parents[1]  # where `app` is importable from
CHILD = [sys.executable, "-B", "-E", "-s", "-m", "app.attachment_sandbox"]
SLOTS = threading.BoundedSemaphore(3)
SLOT_WAIT = 10  # seconds
REASONS = {"type", "too_big", "unreadable", "no_text"}
SUMMARY = re.compile(r"image, \d{1,8}x\d{1,8}|pdf, \d{1,2} pages?|spreadsheet, (first )?\d{1,3} rows?")
PNG = b"\x89PNG\r\n\x1a\n"


def convert_isolated(data: bytes, timeout: float = TIMEOUT) -> Attachment:
    if not SLOTS.acquire(timeout=SLOT_WAIT):
        raise AttachmentRejected("busy")
    try:
        run = subprocess.run(CHILD, input=data, capture_output=True, timeout=timeout, cwd=ROOT, env=_bare_env())
    except subprocess.TimeoutExpired as error:
        raise AttachmentRejected("too_big") from error
    finally:
        SLOTS.release()
    try:
        return _checked(json.loads(run.stdout) if run.returncode == 0 else None)
    except (ValueError, TypeError, KeyError, binascii.Error) as error:
        raise AttachmentRejected("unreadable") from error


def _checked(out: dict) -> Attachment:
    """The child's answer, if it has the only shape a conversion can have; anything else is a ValueError."""
    if not out["ok"]:
        raise AttachmentRejected(out["reason"] if out["reason"] in REASONS else "unreadable")
    kind, summary, text = out["kind"], out["summary"], out.get("text")
    png = base64.b64decode(out["png"], validate=True) if out.get("png") else None
    if not SUMMARY.fullmatch(summary) or summary.split(",")[0] != kind:
        raise ValueError("not a conversion")
    if (kind == "image") != (png is not None and png.startswith(PNG) and text is None):
        raise ValueError("not a conversion")
    if kind != "image" and not (isinstance(text, str) and 0 < len(text) <= TEXT_MAX):
        raise ValueError("not a conversion")
    return Attachment(kind, summary, text, png)


def _bare_env() -> dict[str, str]:
    # Development machines only: Windows can't start Python without SYSTEMROOT, and without SYSTEMDRIVE it writes
    # "%SystemDrive%/ProgramData" caches into the working folder. Neither is a secret.
    return {k: os.environ[k] for k in ("SYSTEMROOT", "SYSTEMDRIVE") if k in os.environ}


def not_dumpable() -> None:
    """Linux: no process of the same user may read this one's environment or memory (/proc/<pid>/environ, mem)."""
    if sys.platform == "linux":
        import ctypes

        if ctypes.CDLL(None, use_errno=True).prctl(4, 0, 0, 0, 0) != 0:  # PR_SET_DUMPABLE, 0
            raise OSError(ctypes.get_errno(), "prctl(PR_SET_DUMPABLE) failed")


not_dumpable()  # the API process, as soon as it can start children: its secrets stay out of their reach


def lock_down() -> None:
    if sys.platform != "linux":
        return  # development machines only; production is Linux and always locked
    import resource

    import pyseccomp as seccomp

    not_dumpable()  # exec made the child dumpable again: hide it from its siblings (another visitor's file)
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY, MEMORY))
    resource.setrlimit(resource.RLIMIT_CPU, (TIMEOUT, TIMEOUT))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    rules = seccomp.SyscallFilter(defaction=seccomp.ALLOW)
    for call in ("socket", "socketpair", "execve", "execveat", "ptrace", "process_vm_readv", "process_vm_writev"):
        rules.add_rule(seccomp.ERRNO(errno.EPERM), call)
    rules.load()


def _child() -> None:
    lock_down()
    data = sys.stdin.buffer.read()
    try:
        c = convert(data)
        out = {"ok": True, "kind": c.kind, "summary": c.summary, "text": c.text,
               "png": base64.b64encode(c.png).decode() if c.png else None}  # fmt: skip
    except AttachmentRejected as refused:
        out = {"ok": False, "reason": str(refused)}
    sys.stdout.write(json.dumps(out))


if __name__ == "__main__":
    _child()
