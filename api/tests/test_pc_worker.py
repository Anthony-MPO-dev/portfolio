"""Chat worker: runs `claude -p` with no tools, MCP, hooks, commands or CLAUDE.md, checks that it really had none
before a single word goes out, streams the answer to the API as it is written, and hands the final text back."""

import json
import subprocess
import threading
import time

import pytest

from worker.pc_worker import Api, Chunks, Unsafe, answer, child_env, command, pick_claude, serve

WORKDIR = "portfolio-worker-empty"  # only handed to the runner, never touched
JOB = {
    "id": "job-1",
    "system": "SYSTEM PROMPT",
    "prompt": "<conversation>{}</conversation>",
    "deadline": time.time() + 60,
}


class Runner:
    """Stands in for the claude process: records the call and yields scripted stdout lines, then fails like the
    real one would (a non-zero exit at the end), or raises at once."""

    def __init__(self, returncode=0, stdout="", error: Exception | None = None):
        self.returncode, self.stdout, self.error = returncode, stdout, error
        self.calls = []

    def __call__(self, cmd, prompt, cwd, timeout):
        self.calls.append({"cmd": cmd, "prompt": prompt, "cwd": cwd, "timeout": timeout})
        if self.error:
            raise self.error
        yield from self.stdout.splitlines()
        if self.returncode:
            raise subprocess.CalledProcessError(self.returncode, cmd)


CLEAN_INIT = {"type": "system", "subtype": "init", "tools": [], "mcp_servers": [], "skills": [], "slash_commands": [],
              "plugins": [{"name": "cc-plugin-privacy", "path": "builtin"}]}  # fmt: skip


def delta(text):
    return {"type": "stream_event", "event": {"type": "content_block_delta", "index": 0,
            "delta": {"type": "text_delta", "text": text}}}  # fmt: skip


def stream(*events, init=CLEAN_INIT, **result):
    """A claude stream-json output: the init event, any other events, then the result event."""
    result_event = {"type": "result", "is_error": False, "permission_denials": [], **result}
    return "\n".join(json.dumps(e) for e in ([init] if init else []) + list(events) + [result_event])


def run_answer(stdout=None, runner=None):
    sent = []
    raw = answer(JOB, runner or Runner(stdout=stdout), emit=sent.append, claude="c", model="haiku", workdir=WORKDIR)
    return raw, sent


def test_claude_runs_with_no_tools_mcp_hooks_or_commands_and_streams_partial_messages():
    cmd = command("claude.exe", JOB, model="haiku")
    pairs = dict(zip(cmd, cmd[1:]))
    assert {"-p", "--restricted", "--safe-mode", "--strict-mcp-config", "--no-session-persistence",
            "--disable-slash-commands", "--verbose", "--include-partial-messages"} <= set(cmd)  # fmt: skip
    assert (pairs["--tools"], pairs["--permission-mode"]) == ("", "dontAsk")
    assert "--allowedTools" not in cmd and "--json-schema" not in cmd  # no tool at all, not even an answer tool
    assert json.loads(pairs["--settings"]) == {"disableAllHooks": True}
    assert (pairs["--input-format"], pairs["--output-format"]) == ("stream-json", "stream-json")
    assert (pairs["--model"], pairs["--system-prompt"]) == ("haiku", "SYSTEM PROMPT")
    assert JOB["prompt"] not in " ".join(cmd)


def test_claude_gets_only_the_environment_it_needs():
    env = child_env({"PATH": "/bin", "USERPROFILE": "C:/Users/a", "HOME": "/home/chat", "CLAUDE_CODE_OAUTH_TOKEN": "o",
                     "PORTFOLIO_WORKER_TOKEN": "secret", "AWS_SECRET_ACCESS_KEY": "x", "GITHUB_TOKEN": "y"})  # fmt: skip
    assert {"PORTFOLIO_WORKER_TOKEN", "AWS_SECRET_ACCESS_KEY", "GITHUB_TOKEN"}.isdisjoint(env)
    assert (env["PATH"], env["HOME"], env["CLAUDE_CODE_OAUTH_TOKEN"]) == ("/bin", "/home/chat", "o")
    for flag in ("CLAUDE_CODE_DISABLE_CLAUDE_MDS", "CLAUDE_CODE_DISABLE_AUTO_MEMORY", "CLAUDE_CODE_DISABLE_ATTACHMENTS",
                 "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "COPILOTO_DESLIGADO"):  # fmt: skip
        assert env[flag] == "1"
    assert env["ENABLE_CLAUDEAI_MCP_SERVERS"] == "false"


def test_visitor_prompt_goes_through_stdin_as_one_stream_json_message_in_an_empty_folder():
    runner = Runner(stdout=stream(result="Hi."))
    run_answer(runner=runner)
    call = runner.calls[0]
    message = json.loads(call["prompt"])
    assert message == {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": JOB["prompt"]}]}}
    assert call["cwd"] == WORKDIR and 0 < call["timeout"] <= 60


def test_images_go_in_the_same_message_as_png_blocks():
    runner = Runner(stdout=stream(result="A red square."))
    answer({**JOB, "images": ["iVBORw0KGgo="]}, runner, claude="c", model="haiku", workdir=WORKDIR)
    content = json.loads(runner.calls[0]["prompt"])["message"]["content"]
    assert content[1] == {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "iVBORw0KGgo="}}


def test_text_streams_out_as_it_is_written_and_the_final_text_comes_back():
    raw, sent = run_answer(stream(delta("He has "), delta("3+ years."), result="He has 3+ years."))
    assert (raw, sent) == ("He has 3+ years.", ["He has ", "3+ years."])


def test_any_failure_hands_back_an_empty_answer():
    failures = [
        Runner(returncode=1, stdout=stream(result="half")),
        Runner(stdout="not json"),
        Runner(stdout=stream(is_error=True, result="quota")),
        Runner(error=subprocess.TimeoutExpired("claude", 1)),
        Runner(error=OSError("claude.exe not found")),
    ]
    assert [run_answer(runner=r)[0] for r in failures] == [""] * 5


@pytest.mark.parametrize(
    "init",
    [
        {**CLEAN_INIT, "tools": ["Read"]},
        {**CLEAN_INIT, "tools": ["StructuredOutput"]},  # no tool at all now, not even this one
        {**CLEAN_INIT, "mcp_servers": [{"name": "crm", "status": "connected"}]},
        {**CLEAN_INIT, "skills": ["deploy"]},
        {**CLEAN_INIT, "slash_commands": ["config"]},
        {**CLEAN_INIT, "plugins": [{"name": "my-plugin", "path": "C:/Users/a/.claude/plugins/my-plugin"}]},
    ],
)
def test_an_unclean_init_stops_the_run_before_a_word_goes_out(init, capsys):
    with pytest.raises(Unsafe):
        run_answer(stream(delta("Sure."), init=init, result="Sure."))
    assert "ALERT" in capsys.readouterr().out


def test_text_before_the_init_event_is_never_trusted():
    sent = []
    with pytest.raises(Unsafe, match="no init"):
        answer(JOB, Runner(stdout=stream(delta("early"), init=None, result="x")), emit=sent.append,
               claude="c", model="haiku", workdir=WORKDIR)  # fmt: skip
    assert sent == []


def test_a_tool_use_or_a_permission_denial_is_refused(capsys):
    tool_use = {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read", "input": {}}]}}
    tool_start = {"type": "stream_event", "event": {"type": "content_block_start", "index": 1,
                  "content_block": {"type": "tool_use", "name": "Bash"}}}  # fmt: skip
    status = {"type": "system", "subtype": "status", "message": "a status line, not a dict"}
    for out in (stream(status, tool_use, result="Done."), stream(tool_start, result="Done."),
                stream(result="Done.", permission_denials=[{"tool_name": "Bash"}])):  # fmt: skip
        with pytest.raises(Unsafe):
            run_answer(out)
    assert capsys.readouterr().out.count("ALERT") == 3


def test_job_past_its_deadline_is_not_run():
    runner = Runner(stdout=stream(result="late"))
    raw = answer({**JOB, "deadline": time.time() - 1}, runner, claude="c", model="haiku", workdir=WORKDIR)
    assert (raw, runner.calls) == ("", [])


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class FakeApi:
    """Hands out scripted poll results (a job, None, or an exception), then stops the loop."""

    def __init__(self, polls, stop: threading.Event):
        self.polls = list(polls)
        self.stop = stop
        self.finished, self.chunks = [], []

    def next_job(self):
        item = self.polls.pop(0)
        if not self.polls:
            self.stop.set()
        if isinstance(item, Exception):
            raise item
        return item

    def chunk(self, job_id, text):
        self.chunks.append((job_id, text))

    def finish(self, job_id, raw, alert=None):
        self.finished.append((job_id, raw) if alert is None else (job_id, raw, alert))


def test_chunks_go_out_in_batches_and_the_rest_on_flush():
    api, clock = FakeApi([], threading.Event()), Clock()
    chunks = Chunks(api, "job-1", every=0.2, clock=clock)
    chunks("He ")
    clock.now = 0.1
    chunks("has ")
    clock.now = 0.3
    chunks("3+ ")
    chunks("years.")
    chunks.flush()
    assert api.chunks == [("job-1", "He has 3+ "), ("job-1", "years.")]


def test_a_chunk_that_fails_to_send_never_stops_the_answer():
    class Down(FakeApi):
        def chunk(self, job_id, text):
            raise OSError("network down")

    api = Down([], threading.Event())
    chunks = Chunks(api, "job-1", every=0, clock=Clock())
    chunks("Hi.")
    chunks(" More.")  # no exception: the final answer still goes out with finish
    chunks.flush()


def test_loop_streams_and_finishes_jobs_and_survives_network_errors():
    stop, sleeps = threading.Event(), []
    api = FakeApi([None, OSError("network down"), OSError("still down"), JOB], stop)

    def handle(job, emit):
        emit("the answer")
        return "the answer"

    serve(api, handle, stop=stop, sleep=sleeps.append)
    assert (api.chunks, api.finished, sleeps) == ([("job-1", "the answer")], [("job-1", "the answer")], [1, 2])


def test_an_unsafe_run_hands_back_an_empty_answer_with_the_alert_and_no_held_text():
    stop = threading.Event()
    api = FakeApi([JOB], stop)

    def handle(job, emit):
        emit("held in the batch")
        raise Unsafe("tool_use in the stream")

    serve(api, handle, stop=stop, sleep=lambda s: None)
    assert (api.chunks, api.finished) == ([], [("job-1", "", "tool_use in the stream")])


class FakeConnection:
    def __init__(self, responses):
        self.responses, self.requests, self.closed = responses, [], False

    def request(self, method, path, body=None, headers=None):
        self.requests.append((method, path, body, headers))
        outcome = self.responses.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        self.pending = outcome

    def getresponse(self):
        status, body = self.pending
        return type("Response", (), {"status": status, "read": lambda self: body})()

    def close(self):
        self.closed = True


def test_the_api_client_keeps_one_connection_for_every_call():
    made = []

    def connect(host, timeout):
        made.append(FakeConnection([(204, b""), (204, b""), (204, b"")]))
        return made[-1]

    api = Api("https://anthonymuniz.dev", "t0ken", connect=connect)
    assert api.next_job() is None
    api.chunk("a" * 32, "Hi")
    api.finish("a" * 32, "Hi.")
    method, path, body, headers = made[0].requests[1]
    assert len(made) == 1 and (method, path) == ("POST", f"/api/worker/jobs/{'a' * 32}/chunks")
    assert json.loads(body) == {"text": "Hi"} and headers["Authorization"] == "Bearer t0ken"


def test_a_dropped_connection_is_reopened_once_for_a_poll_but_a_chunk_is_never_resent():
    made = []
    scripts = [[ConnectionResetError("closed by the server")], [(200, b'{"id": "x"}'), BrokenPipeError("gone")]]

    def connect(host, timeout):
        made.append(FakeConnection(scripts.pop(0)))
        return made[-1]

    api = Api("https://anthonymuniz.dev", "t", connect=connect)
    assert api.next_job() == {"id": "x"}
    with pytest.raises(OSError):
        api.chunk("a" * 32, "Hi")
    assert len(made) == 2 and made[0].closed and made[1].closed  # the chunk was tried once, on the kept connection


def test_an_error_status_is_an_oserror():
    api = Api("https://anthonymuniz.dev", "wrong", connect=lambda host, timeout: FakeConnection([(401, b"")]))
    with pytest.raises(OSError, match="401"):
        api.next_job()


IDE_EXES = [
    "C:/Users/a/.vscode/extensions/anthropic.claude-code-2.1.9-win32-x64/resources/native-binary/claude.exe",
    "C:/Users/a/.vscode/extensions/anthropic.claude-code-2.1.319-win32-x64/resources/native-binary/claude.exe",
]


def test_claude_bin_setting_wins():
    assert pick_claude("D:/tools/claude.exe", "C:/npm/claude.exe", IDE_EXES) == "D:/tools/claude.exe"


def test_native_claude_on_the_path_is_used():
    assert pick_claude(None, "C:/Users/a/.local/bin/claude.exe", IDE_EXES) == "C:/Users/a/.local/bin/claude.exe"


@pytest.mark.parametrize("shim", ["C:/npm/claude.cmd", "C:/npm/claude.CMD", "C:/npm/claude.bat"])
def test_npm_shim_is_skipped_for_the_newest_native_exe(shim):
    """cmd.exe caps a command line at 8191 characters; the system prompt alone is about 12 000."""
    assert pick_claude(None, shim, IDE_EXES) == IDE_EXES[1]


def test_no_usable_claude_gives_none():
    assert pick_claude(None, "C:/npm/claude.cmd", []) is None
