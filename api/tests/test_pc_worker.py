"""Worker on Anthony's PC: runs `claude -p` isolated (no tools, no CLAUDE.md, no MCP) and hands the answer back."""

import json
import subprocess
import threading
import time

from worker.pc_worker import answer, command, serve

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


def claude_output(**fields):
    return json.dumps({"type": "result", "is_error": False, **fields})


def test_claude_runs_isolated_with_the_job_system_prompt_and_schema():
    cmd = command("claude.exe", JOB, model="haiku")
    pairs = dict(zip(cmd, cmd[1:]))
    assert {"-p", "--safe-mode", "--strict-mcp-config", "--no-session-persistence"} <= set(cmd)
    assert (pairs["--tools"], pairs["--model"], pairs["--system-prompt"]) == ("", "haiku", "SYSTEM PROMPT")
    assert json.loads(pairs["--json-schema"]) == JOB["schema"] and JOB["prompt"] not in cmd


def test_visitor_prompt_goes_through_stdin_in_an_empty_folder():
    run = Runner(stdout=claude_output(structured_output={"reply": "Hi.", "offer_contact": False}))
    answer(JOB, run, claude="claude.exe", model="haiku", workdir=WORKDIR)
    call = run.calls[0]
    assert (call["prompt"], call["cwd"]) == (JOB["prompt"], WORKDIR)
    assert 0 < call["timeout"] <= 60


def test_structured_output_is_handed_back_as_json():
    run = Runner(stdout=claude_output(structured_output={"reply": "Hi.", "offer_contact": True}))
    raw = answer(JOB, run, claude="claude.exe", model="haiku", workdir=WORKDIR)
    assert json.loads(raw) == {"reply": "Hi.", "offer_contact": True}


def test_plain_result_is_handed_back_when_there_is_no_structured_output():
    run = Runner(stdout=claude_output(result="He has 3+ years of Python."))
    assert answer(JOB, run, claude="claude.exe", model="haiku", workdir=WORKDIR) == "He has 3+ years of Python."


def test_any_failure_hands_back_an_empty_answer():
    failures = [
        Runner(returncode=1, stdout="boom"),
        Runner(stdout="not json"),
        Runner(stdout=json.dumps({"type": "result", "is_error": True, "result": "quota"})),
        Runner(error=subprocess.TimeoutExpired("claude", 1)),
        Runner(error=OSError("claude.exe not found")),
    ]
    assert [answer(JOB, run, claude="c", model="haiku", workdir=WORKDIR) for run in failures] == [""] * 5


def test_job_past_its_deadline_is_not_run():
    run = Runner(stdout=claude_output(result="late"))
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

    def finish(self, job_id, raw):
        self.finished.append((job_id, raw))


def test_loop_answers_jobs_and_survives_network_errors():
    stop, sleeps = threading.Event(), []
    api = FakeApi([None, OSError("network down"), OSError("still down"), JOB], stop)
    serve(api, lambda job: "the answer", stop=stop, sleep=sleeps.append)
    assert (api.finished, sleeps) == ([("job-1", "the answer")], [1, 2])
