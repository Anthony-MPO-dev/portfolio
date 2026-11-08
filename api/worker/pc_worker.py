"""Chat worker: answers the portfolio chat with `claude -p`, meant to run in its own isolated WSL distro or VM.

Responsibility: long-poll the API over HTTPS with a secret token (only outbound connections: no port open at home,
no Redis exposed), run `claude -p` hardened for each job, check it really was, and hand the raw answer back.
Hardening (pesquisa-seguranca-chat-portfolio.md, section 3): --restricted and --safe-mode, no built-in tools, dontAsk
with only the StructuredOutput answer tool allowed, no MCP, hooks, commands or saved session, an empty working
folder, the job's own system prompt and JSON schema, and an environment with only what claude needs (the worker
token never reaches it; CLAUDE.md, memory, @-attachments and claude.ai connectors switched off). The visitor's text
goes through stdin as one stream-json message, never the command line. Checks on every run: the init event lists no
tool but the answer tool, no MCP server, skill or command and only built-in plugins, and no other tool_use or
permission denial follows; a miss drops the answer and logs an ALERT. Any failure hands back an empty answer, which
the API shows as "offline". Nothing about the visitor is logged here, only the job id and how it went. Standard
library only, so it runs with any Python 3.12+. It lives outside app/ so the API image never ships it.
Public API: command, child_env, stdin_message, unsafe, answer, serve, Api, run_claude, pick_claude, find_claude,
log, main. Run: `python -m worker.pc_worker` from api/, with PORTFOLIO_WORKER_TOKEN set (and PORTFOLIO_API to point
at a local API while testing).
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
from collections.abc import Callable, Mapping
from functools import partial
from pathlib import Path

Runner = Callable[[list[str], str, str, float], tuple[int, str]]


def command(claude: str, job: dict, model: str) -> list[str]:
    return [
        claude, "-p", "--restricted", "--safe-mode", "--tools", "", "--allowedTools", ANSWER_TOOL, "--strict-mcp-config",
        "--disable-slash-commands", "--no-session-persistence", "--permission-mode", "dontAsk",
        "--permission-prompts", "none", "--settings", json.dumps({"disableAllHooks": True}), "--max-budget-usd", "0.25",
        "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
        "--system-prompt", job["system"], "--json-schema", json.dumps(job["schema"]), "--model", model,
    ]  # fmt: skip


# What claude needs to start and log in (Windows or Linux); everything else, the worker token included, stays out.
PASS_THROUGH = ("PATH", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "SYSTEMROOT", "SYSTEMDRIVE", "TEMP", "TMP",
                "CLAUDE_CONFIG_DIR", "CLAUDE_CODE_OAUTH_TOKEN")  # fmt: skip
HARDENING = {
    "CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1",
    "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
    "CLAUDE_CODE_DISABLE_ATTACHMENTS": "1",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    "ENABLE_CLAUDEAI_MCP_SERVERS": "false",
    "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "1500",
    "COPILOTO_DESLIGADO": "1",
}


def child_env(env: Mapping[str, str]) -> dict[str, str]:
    return {key: env[key] for key in PASS_THROUGH if key in env} | HARDENING


def stdin_message(job: dict) -> str:
    return json.dumps({"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": job["prompt"]}]}})


ANSWER_TOOL = "StructuredOutput"  # added by --json-schema; its only effect is handing back the reply JSON


def unsafe(events: list[dict]) -> str | None:
    """Why this run can't be trusted, or None. The init event must show no tool but the answer tool, no MCP server,
    skill or command, and only the plugins built into the binary; no other tool_use and no permission denial."""
    init = next((e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), None)
    if init is None:
        return "no init event"
    if set(init.get("tools") or []) - {ANSWER_TOOL}:
        return "init has tools"
    for key in ("mcp_servers", "skills", "slash_commands"):
        if init.get(key):
            return f"init has {key}"
    if any(p.get("path") != "builtin" for p in init.get("plugins") or []):
        return "init has an installed plugin"
    for event in events:
        message = event.get("message")
        for block in message.get("content") or [] if isinstance(message, dict) else []:
            if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") != ANSWER_TOOL:
                return "tool_use in the stream"
        if event.get("type") == "result" and event.get("permission_denials"):
            return "permission denial"
    return None


class Unsafe(Exception):
    """The run wasn't clean (a tool, an MCP server, a denial...): the answer is dropped and Anthony is alerted."""


def answer(job: dict, run: Runner, *, claude: str, model: str, workdir: str) -> str:
    timeout = job["deadline"] - time.time()
    if timeout <= 1:
        return ""  # the visitor already got "offline"
    try:
        code, out = run(command(claude, job, model), stdin_message(job), workdir, timeout)
        events = [json.loads(line) for line in out.splitlines() if line.strip()] if code == 0 else []
    except (OSError, ValueError, subprocess.SubprocessError):
        return ""
    result = next((e for e in events if isinstance(e, dict) and e.get("type") == "result"), None)
    if not result or result.get("is_error"):
        return ""
    if reason := unsafe(events):
        log(f"ALERT job {str(job.get('id'))[:8]}: {reason}; answer dropped")
        raise Unsafe(reason)
    if isinstance(result.get("structured_output"), dict):
        return json.dumps(result["structured_output"], ensure_ascii=False)
    return str(result.get("result") or "")


def serve(api, handle: Callable[[dict], str], stop: threading.Event | None = None, sleep=time.sleep) -> None:
    backoff = 1
    while not (stop and stop.is_set()):
        try:
            job = api.next_job()
            if job:
                started = time.monotonic()
                try:
                    raw, alert = handle(job), None
                except Unsafe as error:
                    raw, alert = "", str(error)
                api.finish(job["id"], raw, alert)
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

    def finish(self, job_id: str, raw: str, alert: str | None = None) -> None:
        body = {"answer": raw} if alert is None else {"answer": raw, "alert": alert}
        self._open(f"/api/worker/jobs/{job_id}", body).close()


def run_claude(cmd: list[str], prompt: str, cwd: str, timeout: float) -> tuple[int, str]:
    done = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=cwd,
        env=child_env(os.environ),
        timeout=timeout,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return done.returncode, done.stdout


def pick_claude(setting: str | None, on_path: str | None, ide_exes: list[str]) -> str | None:
    """CLAUDE_BIN, else a native claude on the PATH, else the newest claude.exe from an IDE extension.

    An npm .cmd/.bat shim is skipped: cmd.exe caps a command line at 8191 characters and the system prompt alone is
    about 12 000.
    """
    if setting:
        return setting
    if on_path and Path(on_path).suffix.lower() not in (".cmd", ".bat"):
        return on_path

    def version(path: str) -> tuple[int, ...]:
        numbers = Path(path).parts[-4].removeprefix("anthropic.claude-code-").split("-")[0]
        return tuple(int(n) for n in numbers.split(".") if n.isdigit())

    return max(ide_exes, key=version) if ide_exes else None


def find_claude() -> str:
    ide_exes = [
        str(path)
        for ide in (".antigravity-ide", ".vscode", ".cursor")
        for path in Path.home().glob(f"{ide}/extensions/anthropic.claude-code-*/resources/native-binary/claude.exe")
    ]
    return pick_claude(os.environ.get("CLAUDE_BIN"), shutil.which("claude"), ide_exes) or sys.exit(
        "no native claude found (an npm .cmd shim can't take the system prompt): set CLAUDE_BIN"
    )


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
