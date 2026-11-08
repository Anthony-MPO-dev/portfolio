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
- the parent waits at most 20 s; a hang, a crash or nonsense output is a refusal.
Public API: convert_isolated, lock_down, CHILD.
Used by: app.main (the chat use case's attachment converter).
Depends on: app.attachments (run in the child), pyseccomp and resource (Linux only).
Tests: tests/test_attachment_sandbox.py (the lock-down tests run on Linux, in the API image).
"""

import base64
import errno
import json
import os
import subprocess
import sys
from pathlib import Path

from app.attachments import Converted, Rejected, convert

TIMEOUT = 20  # seconds, wall clock in the parent and CPU in the child
MEMORY = 512 * 1024 * 1024
ROOT = Path(__file__).resolve().parents[1]  # where `app` is importable from
CHILD = [sys.executable, "-B", "-E", "-s", "-m", "app.attachment_sandbox"]


def convert_isolated(data: bytes, timeout: float = TIMEOUT) -> Converted:
    try:
        run = subprocess.run(CHILD, input=data, capture_output=True, timeout=timeout, cwd=ROOT, env=_bare_env())
    except subprocess.TimeoutExpired as error:
        raise Rejected("too_big") from error
    try:
        out = json.loads(run.stdout) if run.returncode == 0 else None
    except ValueError:
        out = None
    if not isinstance(out, dict):
        raise Rejected("unreadable")
    if not out.get("ok"):
        raise Rejected(str(out.get("reason", "unreadable")))
    image = base64.b64decode(out["png"]) if out.get("png") else None
    return Converted(out["kind"], out["summary"], out.get("text"), image)


def _bare_env() -> dict[str, str]:
    # Development machines only: Windows can't start Python without SYSTEMROOT, and without SYSTEMDRIVE it writes
    # "%SystemDrive%/ProgramData" caches into the working folder. Neither is a secret.
    return {k: os.environ[k] for k in ("SYSTEMROOT", "SYSTEMDRIVE") if k in os.environ}


def lock_down() -> None:
    if sys.platform != "linux":
        return  # development machines only; production is Linux and always locked
    import resource

    import pyseccomp as seccomp

    resource.setrlimit(resource.RLIMIT_AS, (MEMORY, MEMORY))
    resource.setrlimit(resource.RLIMIT_CPU, (TIMEOUT, TIMEOUT))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    rules = seccomp.SyscallFilter(defaction=seccomp.ALLOW)
    for call in ("socket", "socketpair", "execve", "execveat"):
        rules.add_rule(seccomp.ERRNO(errno.EPERM), call)
    rules.load()


def _child() -> None:
    lock_down()
    data = sys.stdin.buffer.read()
    try:
        c = convert(data)
        out = {"ok": True, "kind": c.kind, "summary": c.summary, "text": c.text,
               "png": base64.b64encode(c.png).decode() if c.png else None}  # fmt: skip
    except Rejected as refused:
        out = {"ok": False, "reason": str(refused)}
    sys.stdout.write(json.dumps(out))


if __name__ == "__main__":
    _child()
