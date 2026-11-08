"""Chat worker: answers the portfolio chat with `claude -p`, meant to run in its own isolated WSL distro or VM.

Responsibility: long-poll the API over one kept-alive HTTPS connection with a secret token (only outbound
connections: no port open at home, no Redis exposed), run `claude -p` hardened for each job, stream the answer's text
to the API as it is written (in batches of about 0.2 s), and hand the final text back.
Hardening (pesquisa-seguranca-chat-portfolio.md, section 3): --restricted and --safe-mode, no tools at all (--tools ""
and --disallowedTools "*", two independent locks), one turn, dontAsk, no MCP, hooks, commands or saved session, an
empty working folder, the job's own system prompt, and an environment with only what claude needs (the worker token
never reaches it; CLAUDE.md, memory, @-attachments and claude.ai connectors switched off). The visitor's text, and
any attachment image, goes through stdin as one stream-json message, never the command line. Checks on every run,
before a word goes out: the first event must be a clean init (no tool, no MCP server, skill or command, only built-in
plugins); after it, any tool block (tool_use, server_tool_use, mcp_tool_use; whole or streamed) or permission denial
stops the run. A miss drops the answer, logs an ALERT and hands the API the alert label. Any other failure hands
back an empty answer, which the API shows as "offline". Nothing about the visitor is logged here: one
line per run with the job id, sizes, cost and time. Three failed runs in a row (claude down, logged out or out of
quota) send Anthony one alert. Standard library only, so it runs with any Python 3.12+. It lives outside app/ so the
API image never ships it.
Public API: command, child_env, stdin_message, unsafe_init, unsafe_event, delta_text, answer, Unsafe, Chunks, serve,
Api, stream_claude, pick_claude, find_claude, log, main. Run: `python -m worker.pc_worker` from api/, with
PORTFOLIO_WORKER_TOKEN set (and PORTFOLIO_API to point at a local API while testing).
Used by: the isolated distro on Anthony's PC (ops/wsl-chat.ps1).
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
import http.client
from collections.abc import Callable, Iterator, Mapping

from pathlib import Path
from urllib.parse import urlsplit

Runner = Callable[[list[str], str, str, float], Iterator[str]]  # yields claude's stdout lines


def command(claude: str, job: dict, model: str) -> list[str]:
    return [
        claude, "-p", "--restricted", "--safe-mode", "--tools", "", "--disallowedTools", "*", "--max-turns", "1",
        "--strict-mcp-config",
        "--disable-slash-commands", "--no-session-persistence", "--permission-mode", "dontAsk",
        "--permission-prompts", "none", "--settings", json.dumps({"disableAllHooks": True}), "--max-budget-usd", "0.25",
        "--input-format", "stream-json", "--output-format", "stream-json", "--verbose", "--include-partial-messages",
        "--system-prompt", job["system"], "--model", model,
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
    """One user message: the conversation text, then any attachment images (fresh PNGs made by the API)."""
    content = [{"type": "text", "text": job["prompt"]}] + [
        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": data}}
        for data in job.get("images") or []
    ]
    return json.dumps({"type": "user", "message": {"role": "user", "content": content}})


def unsafe_init(init: dict) -> str | None:
    """The init event must show no tool at all, no MCP server, skill or command, and only built-in plugins."""
    if init.get("tools"):
        return "init has tools"
    for key in ("mcp_servers", "skills", "slash_commands"):
        if init.get(key):
            return f"init has {key}"
    if any(p.get("path") != "builtin" for p in init.get("plugins") or []):
        return "init has an installed plugin"
    return None


def unsafe_event(event: dict) -> str | None:
    """No tool_use, whole or streamed, and no permission denial, anywhere after init."""
    message = event.get("message")
    for block in message.get("content") or [] if isinstance(message, dict) else []:
        if isinstance(block, dict) and _is_tool(block):
            return "tool_use in the stream"
    inner = event.get("event") if event.get("type") == "stream_event" else None
    if isinstance(inner, dict) and _is_tool(inner.get("content_block") or {}):
        return "tool_use in the stream"
    if event.get("type") == "result" and event.get("permission_denials"):
        return "permission denial"
    return None


def _is_tool(block: dict) -> bool:
    return str(block.get("type")).endswith("tool_use")  # tool_use, server_tool_use, mcp_tool_use...


def delta_text(event: dict) -> str:
    inner = event.get("event") if event.get("type") == "stream_event" else None
    if isinstance(inner, dict) and inner.get("type") == "content_block_delta":
        delta = inner.get("delta") or {}
        if delta.get("type") == "text_delta":
            return str(delta.get("text") or "")
    return ""


class Unsafe(Exception):
    """The run wasn't clean (a tool, an MCP server, a denial...): the answer is dropped and Anthony is alerted."""


def _is_init(event: dict) -> bool:
    return event.get("type") == "system" and event.get("subtype") == "init"


def answer(job: dict, run: Runner, *, emit: Callable[[str], None] = lambda text: None, claude: str, model: str,
           workdir: str) -> str:  # fmt: skip
    """Stream the answer's text through `emit` as claude writes it and return the final text ("" on any failure).
    Nothing is emitted before a clean init event; an unclean run raises Unsafe."""
    timeout = job["deadline"] - time.time()
    if timeout <= 1:
        return ""  # the visitor already got "offline"
    seen_init, result = False, None
    try:
        for line in run(command(claude, job, model), stdin_message(job), workdir, timeout):
            if not line.strip():
                continue
            event = json.loads(line)
            if not isinstance(event, dict):
                continue
            reason = None
            if _is_init(event):
                seen_init, reason = True, unsafe_init(event)
            elif not seen_init and event.get("type") != "system":
                reason = "no init event"
            else:
                reason = unsafe_event(event)
            if reason:
                raise _unsafe(job, reason)
            if text := delta_text(event):
                emit(text)
            if event.get("type") == "result":
                result = event
    except (OSError, ValueError, subprocess.SubprocessError):
        return ""
    if not seen_init:
        raise _unsafe(job, "no init event")
    if result:  # sizes, cost and time only, never the text
        images = len(job.get("images") or [])
        log(f"job {str(job.get('id'))[:8]}: {'error' if result.get('is_error') else 'done'}, prompt "
            f"{len(job['prompt'])} chars, {images} image{'' if images == 1 else 's'}, "
            f"${float(result.get('total_cost_usd') or 0):.4f}, {result.get('duration_ms')} ms")  # fmt: skip
    if not result or result.get("is_error"):
        return ""
    return str(result.get("result") or "")


def _unsafe(job: dict, reason: str) -> Unsafe:
    log(f"ALERT job {str(job.get('id'))[:8]}: {reason}; answer dropped")
    return Unsafe(reason)


class Chunks:
    """Collects streamed text and sends it to the API every `every` seconds; a failed send stops the streaming for
    this job but never the answer, which still goes out whole with finish."""

    def __init__(self, api, job_id: str, every: float = 0.2, clock: Callable[[], float] = time.monotonic):
        self.api, self.job_id, self.every, self.clock = api, job_id, every, clock
        self.buffer, self.last, self.broken = "", clock(), False

    def __call__(self, text: str) -> None:
        self.buffer += text
        if self.clock() - self.last >= self.every:
            self.flush()

    def flush(self) -> None:
        if self.buffer and not self.broken:
            try:
                self.api.chunk(self.job_id, self.buffer)
            except OSError:
                self.broken = True
        self.buffer, self.last = "", self.clock()


FAILURES_ALERT = 3


def serve(api, handle: Callable[[dict, Callable[[str], None]], str], stop: threading.Event | None = None,
          sleep=time.sleep) -> None:  # fmt: skip
    backoff, failures = 1, 0
    while not (stop and stop.is_set()):
        try:
            job = api.next_job()
            if job:
                started, chunks = time.monotonic(), Chunks(api, job["id"])
                try:
                    raw, alert = handle(job, chunks), None
                    chunks.flush()
                except Unsafe as error:
                    raw, alert = "", str(error)  # whatever was still held is dropped, never sent
                failures = 0 if raw or alert else failures + 1
                if failures == FAILURES_ALERT:  # once per streak: claude is down, logged out or out of quota
                    alert = f"{FAILURES_ALERT} runs in a row failed (timeout or error)"
                api.finish(job["id"], raw, alert)
                log(f"job {job['id'][:8]}: {'ok' if raw else 'failed'} in {time.monotonic() - started:.1f}s")
            backoff = 1
        except (OSError, ValueError) as error:  # network down, API restarting, wrong token
            log(f"API unreachable ({error.__class__.__name__}: {error}); retrying in {backoff}s")
            sleep(backoff)
            backoff = min(backoff * 2, 60)


def _connect(host: str, timeout: float) -> http.client.HTTPSConnection:
    return http.client.HTTPSConnection(host, timeout=timeout)


class Api:
    """The API's worker routes over one kept-alive HTTPS connection. A poll or a finish that finds the connection
    dropped reopens it once; a chunk is never sent twice (the final answer covers anything lost)."""

    def __init__(self, base: str, token: str, wait: int = 20, connect=_connect):
        parts = urlsplit(base)
        self.base, self.host, self.prefix = base.rstrip("/"), parts.netloc, parts.path.rstrip("/")
        self.token, self.wait, self.connect, self.conn = token, wait, connect, None

    def _request(self, method: str, path: str, body: dict | None, timeout: float, retry: bool) -> tuple[int, bytes]:
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json",
                   "User-Agent": "portfolio-worker/1"}  # fmt: skip
        payload = None if body is None else json.dumps(body).encode()
        for attempt in (1, 2):
            if self.conn is None:
                self.conn = self.connect(self.host, timeout)
            elif getattr(self.conn, "sock", None) is not None:
                self.conn.sock.settimeout(timeout)
            try:
                self.conn.request(method, self.prefix + path, body=payload, headers=headers)
                response = self.conn.getresponse()
                data = response.read()
            except (OSError, http.client.HTTPException) as error:
                self.conn.close()
                self.conn = None
                if attempt == 2 or not retry:
                    raise OSError(f"{error.__class__.__name__}: {error}") from error
                continue
            if not 200 <= response.status < 300:
                raise OSError(f"API answered {response.status}")
            return response.status, data
        raise OSError("unreachable")  # pragma: no cover

    def next_job(self) -> dict | None:
        status, data = self._request("GET", f"/api/worker/next?wait={self.wait}", None, self.wait + 15, retry=True)
        return json.loads(data) if status == 200 else None

    def chunk(self, job_id: str, text: str) -> None:
        self._request("POST", f"/api/worker/jobs/{job_id}/chunks", {"text": text}, 10, retry=False)

    def finish(self, job_id: str, raw: str, alert: str | None = None) -> None:
        body = {"answer": raw} if alert is None else {"answer": raw, "alert": alert}
        self._request("POST", f"/api/worker/jobs/{job_id}", body, 15, retry=True)


def stream_claude(cmd: list[str], prompt: str, cwd: str, timeout: float) -> Iterator[str]:
    """Run claude and yield its stdout lines as they come; killed at the deadline; a non-zero exit raises."""
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        cwd=cwd,
        env=child_env(os.environ),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    timer = threading.Timer(timeout, proc.kill)
    timer.start()
    try:
        proc.stdin.write(prompt)
        proc.stdin.close()
        yield from proc.stdout
        if proc.wait() != 0:
            raise subprocess.CalledProcessError(proc.returncode, cmd[0])
    finally:
        timer.cancel()
        if proc.poll() is None:
            proc.kill()


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
    serve(api, lambda job, emit: answer(job, stream_claude, emit=emit, claude=claude, model=model, workdir=workdir))


if __name__ == "__main__":
    main()
