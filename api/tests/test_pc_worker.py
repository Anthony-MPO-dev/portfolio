"""Chat worker: runs `claude -p` with no tools, MCP, hooks, commands or CLAUDE.md, checks that it really had none,
and hands the answer back."""

import json
import subprocess
import threading
import time

import pytest

from worker.pc_worker import Unsafe, answer, child_env, command, pick_claude, serve

WORKDIR = "portfolio-worker-empty"  # only handed to the runner, never touched
JOB = {
    "id": "job-1",
    "system": "SYSTEM PROMPT",
    "prompt": "<visitor_message>hi</visitor_message>",
    "schema": {"type": "object"},
    "deadline": time.time() + 60,
}


class Runner:
    """Stands in for subprocess: records the call and returns a scripted (returncode, stdout), or raises."""

    def __init__(self, returncode=0, stdout="", error: Exception | None = None):
        self.result = (returncode, stdout)
        self.error = error
        self.calls = []

    def __call__(self, cmd, prompt, cwd, timeout):
        self.calls.append({"cmd": cmd, "prompt": prompt, "cwd": cwd, "timeout": timeout})
        if self.error:
            raise self.error
        return self.result


CLEAN_INIT = {"type": "system", "subtype": "init", "tools": [], "mcp_servers": [], "skills": [], "slash_commands": [],
              "plugins": [{"name": "cc-plugin-privacy", "path": "builtin"}]}


def stream(*events, init=CLEAN_INIT, **result):
    """A claude stream-json output: the init event, any other events, then the result event."""
    result_event = {"type": "result", "is_error": False, "permission_denials": [], **result}
    return "\n".join(json.dumps(e) for e in ([init] if init else []) + list(events) + [result_event])


def test_claude_runs_with_no_tools_mcp_hooks_or_commands_and_streams_json():
    cmd = command("claude.exe", JOB, model="haiku")
    pairs = dict(zip(cmd, cmd[1:]))
    assert {"-p", "--restricted", "--safe-mode", "--strict-mcp-config", "--no-session-persistence",
            "--disable-slash-commands", "--verbose"} <= set(cmd)  # fmt: skip
    # dontAsk denies every tool not allowed by name; the answer tool is the only one (a deny-all "*" would beat it)
    assert (pairs["--tools"], pairs["--allowedTools"], pairs["--permission-mode"]) == ("", "StructuredOutput", "dontAsk")
    assert json.loads(pairs["--settings"]) == {"disableAllHooks": True}
    assert (pairs["--input-format"], pairs["--output-format"]) == ("stream-json", "stream-json")
    assert (pairs["--model"], pairs["--system-prompt"]) == ("haiku", "SYSTEM PROMPT")
    assert json.loads(pairs["--json-schema"]) == JOB["schema"] and JOB["prompt"] not in " ".join(cmd)


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
    run = Runner(stdout=stream(structured_output={"reply": "Hi.", "offer_contact": False}))
    answer(JOB, run, claude="claude.exe", model="haiku", workdir=WORKDIR)
    call = run.calls[0]
    message = json.loads(call["prompt"])
    assert message == {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": JOB["prompt"]}]}}
    assert call["cwd"] == WORKDIR and 0 < call["timeout"] <= 60


def test_structured_output_is_handed_back_as_json():
    run = Runner(stdout=stream(structured_output={"reply": "Hi.", "offer_contact": True}))
    raw = answer(JOB, run, claude="claude.exe", model="haiku", workdir=WORKDIR)
    assert json.loads(raw) == {"reply": "Hi.", "offer_contact": True}


def test_plain_result_is_handed_back_when_there_is_no_structured_output():
    run = Runner(stdout=stream(result="He has 3+ years of Python."))
    assert answer(JOB, run, claude="claude.exe", model="haiku", workdir=WORKDIR) == "He has 3+ years of Python."


def test_any_failure_hands_back_an_empty_answer():
    failures = [
        Runner(returncode=1, stdout="boom"),
        Runner(stdout="not json"),
        Runner(stdout=stream(is_error=True, result="quota")),
        Runner(error=subprocess.TimeoutExpired("claude", 1)),
        Runner(error=OSError("claude.exe not found")),
    ]
    assert [answer(JOB, run, claude="c", model="haiku", workdir=WORKDIR) for run in failures] == [""] * 5


@pytest.mark.parametrize(
    "init",
    [
        None,  # nothing to check means nothing to trust
        {**CLEAN_INIT, "tools": ["Read"]},
        {**CLEAN_INIT, "mcp_servers": [{"name": "crm", "status": "connected"}]},
        {**CLEAN_INIT, "skills": ["deploy"]},
        {**CLEAN_INIT, "slash_commands": ["config"]},
        {**CLEAN_INIT, "plugins": [{"name": "my-plugin", "path": "C:/Users/a/.claude/plugins/my-plugin"}]},
    ],
)
def test_an_init_with_any_tool_server_skill_or_installed_plugin_is_refused(init, capsys):
    run = Runner(stdout=stream(init=init, result="Sure."))
    with pytest.raises(Unsafe):
        answer(JOB, run, claude="c", model="haiku", workdir=WORKDIR)
    assert "ALERT" in capsys.readouterr().out


def test_the_structured_output_tool_is_the_only_one_allowed():
    init = {**CLEAN_INIT, "tools": ["StructuredOutput"]}
    call = {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "StructuredOutput", "input": {}}]}}
    status = {"type": "system", "subtype": "status", "message": "a status line, not a dict"}
    out = stream(status, call, init=init, structured_output={"reply": "Hi.", "offer_contact": False})
    assert json.loads(answer(JOB, Runner(stdout=out), claude="c", model="haiku", workdir=WORKDIR))["reply"] == "Hi."
    out = stream(call, init={**init, "tools": ["StructuredOutput", "Read"]}, structured_output={"reply": "Hi."})
    with pytest.raises(Unsafe, match="tools"):
        answer(JOB, Runner(stdout=out), claude="c", model="haiku", workdir=WORKDIR)


def test_a_tool_use_or_a_permission_denial_is_refused(capsys):
    tool_use = {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read", "input": {}}]}}
    for out in (stream(tool_use, result="Done."), stream(result="Done.", permission_denials=[{"tool_name": "Bash"}])):
        with pytest.raises(Unsafe):
            answer(JOB, Runner(stdout=out), claude="c", model="haiku", workdir=WORKDIR)
    assert capsys.readouterr().out.count("ALERT") == 2


def test_job_past_its_deadline_is_not_run():
    run = Runner(stdout=stream(result="late"))
    raw = answer({**JOB, "deadline": time.time() - 1}, run, claude="c", model="haiku", workdir=WORKDIR)
    assert (raw, run.calls) == ("", [])


class FakeApi:
    """Hands out scripted poll results (a job, None, or an exception), then stops the loop."""

    def __init__(self, polls, stop: threading.Event):
        self.polls = list(polls)
        self.stop = stop
        self.finished = []

    def next_job(self):
        item = self.polls.pop(0)
        if not self.polls:
            self.stop.set()
        if isinstance(item, Exception):
            raise item
        return item

    def finish(self, job_id, raw, alert=None):
        self.finished.append((job_id, raw) if alert is None else (job_id, raw, alert))


def test_loop_answers_jobs_and_survives_network_errors():
    stop, sleeps = threading.Event(), []
    api = FakeApi([None, OSError("network down"), OSError("still down"), JOB], stop)
    serve(api, lambda job: "the answer", stop=stop, sleep=sleeps.append)
    assert (api.finished, sleeps) == ([("job-1", "the answer")], [1, 2])


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


def test_an_unsafe_run_hands_back_an_empty_answer_with_the_alert():
    stop = threading.Event()
    api = FakeApi([JOB], stop)

    def handle(job):
        raise Unsafe("tool_use: Read")

    serve(api, handle, stop=stop, sleep=lambda s: None)
    assert api.finished == [("job-1", "", "tool_use: Read")]
