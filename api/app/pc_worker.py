"""Worker on Anthony's PC: answers the portfolio chat with the Claude Code login on this machine.

Responsibility: long-poll the API over HTTPS with a secret token (only outbound connections: no port open at home,
no Redis exposed), run `claude -p` fully isolated for each job, and hand the raw answer back. Isolation: --safe-mode
(no CLAUDE.md, skills, plugins, hooks or MCP servers), no tools, no session saved, an empty working folder, the
job's own system prompt and JSON schema, COPILOTO_DESLIGADO=1. The visitor's text goes through stdin, never the
command line. Any failure hands back an empty answer, which the API shows as "offline". Nothing about the visitor is
logged here, only the job id and how it went. Standard library only, so it runs with any Python 3.12+.
Public API: command, answer, serve, Api, main. Run: `python -m app.pc_worker` from api/, with
PORTFOLIO_WORKER_TOKEN set (and PORTFOLIO_API to point at a local API while testing).
Used by: Anthony's PC (started at login).
Depends on: the claude CLI, the API's /api/worker routes.
Tests: tests/test_pc_worker.py.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from collections.abc import Callable
from functools import partial
from pathlib import Path

Runner = Callable[[list[str], str, str, float], tuple[int, str]]


def command(claude: str, job: dict, model: str) -> list[str]:
    return [
        claude, "-p", "--safe-mode", "--output-format", "json", "--no-session-persistence",
        "--strict-mcp-config", "--disable-slash-commands", "--tools", "",
        "--system-prompt", job["system"], "--json-schema", json.dumps(job["schema"]), "--model", model,
    ]  # fmt: skip


def answer(job: dict, run: Runner, *, claude: str, model: str, workdir: str) -> str:
    timeout = job["deadline"] - time.time()
    if timeout <= 1:
        return ""  # the visitor already got "offline"
    try:
        code, out = run(command(claude, job, model), job["prompt"], workdir, timeout)
        data = json.loads(out) if code == 0 else {}
    except (OSError, ValueError, subprocess.SubprocessError):
        return ""
    if not isinstance(data, dict) or data.get("is_error"):
        return ""
    if isinstance(data.get("structured_output"), dict):
        return json.dumps(data["structured_output"], ensure_ascii=False)
    return str(data.get("result") or "")


def serve(api, handle: Callable[[dict], str], stop: threading.Event | None = None, sleep=time.sleep) -> None:
    backoff = 1
    while not (stop and stop.is_set()):
        try:
            job = api.next_job()
            if job:
                started = time.monotonic()
                raw = handle(job)
                api.finish(job["id"], raw)
                log(f"job {job['id'][:8]}: {'ok' if raw else 'failed'} in {time.monotonic() - started:.1f}s")
            backoff = 1
        except (OSError, ValueError) as error:  # network down, API restarting, wrong token
            log(f"API unreachable ({error.__class__.__name__}: {error}); retrying in {backoff}s")
            sleep(backoff)
            backoff = min(backoff * 2, 60)


class Api:
    def __init__(self, base: str, token: str, wait: int = 20):
        self.base = base.rstrip("/")
        self.token = token
        self.wait = wait

    def _open(self, path: str, body: dict | None = None, timeout: float = 15):
        request = urllib.request.Request(
            self.base + path,
            data=None if body is None else json.dumps(body).encode(),
            method="GET" if body is None else "POST",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "User-Agent": "portfolio-worker/1",
            },
        )
        return urllib.request.urlopen(request, timeout=timeout)

    def next_job(self) -> dict | None:
        with self._open(f"/api/worker/next?wait={self.wait}", timeout=self.wait + 15) as response:
            return json.load(response) if response.status == 200 else None

    def finish(self, job_id: str, raw: str) -> None:
        self._open(f"/api/worker/jobs/{job_id}", {"answer": raw}).close()


def run_claude(cmd: list[str], prompt: str, cwd: str, timeout: float) -> tuple[int, str]:
    done = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=cwd,
        env=dict(os.environ, COPILOTO_DESLIGADO="1"),
        timeout=timeout,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return done.returncode, done.stdout


def find_claude() -> str:
    """CLAUDE_BIN, the PATH, or the newest claude.exe that ships with an IDE extension."""
    found = os.environ.get("CLAUDE_BIN") or shutil.which("claude")
    if found:
        return found
    candidates = [
        path
        for ide in (".antigravity-ide", ".vscode", ".cursor")
        for path in Path.home().glob(f"{ide}/extensions/anthropic.claude-code-*/resources/native-binary/claude.exe")
    ]
    if not candidates:
        sys.exit("claude CLI not found: set CLAUDE_BIN")

    def version(path: Path) -> tuple[int, ...]:
        numbers = path.parts[-4].removeprefix("anthropic.claude-code-").split("-")[0]
        return tuple(int(n) for n in numbers.split(".") if n.isdigit())

    return str(max(candidates, key=version))


def log(message: str) -> None:
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}", flush=True)


def main() -> None:
    token = os.environ.get("PORTFOLIO_WORKER_TOKEN") or sys.exit("set PORTFOLIO_WORKER_TOKEN")
    api = Api(os.environ.get("PORTFOLIO_API", "https://anthonymuniz.dev"), token)
    claude = find_claude()
    model = os.environ.get("PORTFOLIO_WORKER_MODEL", "haiku")
    workdir = tempfile.mkdtemp(prefix="portfolio-worker-")
    log(f"worker up: {api.base}, model {model}")
    serve(api, partial(answer, run=run_claude, claude=claude, model=model, workdir=workdir))


if __name__ == "__main__":
    main()
