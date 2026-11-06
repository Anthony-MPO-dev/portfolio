"""Worker queue: the ChatModel that hands each request to Anthony's PC through Redis, and the worker's side of it.

Runs on fakeredis by default; set REDIS_TEST_URL (local Redis only) to run on a real server too.
"""

import json
import os
import threading
import time
from urllib.parse import urlparse

import fakeredis
import pytest
import redis

from app.adapters.worker_queue import WorkerQueue
from app.ports import ModelReply, ModelUnavailable

BACKENDS = ["fakeredis"] + (["redis"] if os.environ.get("REDIS_TEST_URL") else [])
HELLO = [{"role": "user", "content": "Who is he?"}, {"role": "assistant", "content": "An AI engineer."}]


@pytest.fixture(params=BACKENDS)
def r(request):
    if request.param == "fakeredis":
        client = fakeredis.FakeRedis(server=fakeredis.FakeServer(), decode_responses=True)
    else:
        url = os.environ["REDIS_TEST_URL"]
        assert urlparse(url).hostname in ("localhost", "127.0.0.1"), "these tests flush the database"
        client = redis.Redis.from_url(url, decode_responses=True)
    client.flushdb()
    yield client
    client.flushdb()


def make(r, timeout=2):
    return WorkerQueue(r, system="SYSTEM PROMPT", timeout=timeout)


def worker_answers(queue: WorkerQueue, raw: str, seen: list | None = None):
    """Start a fake PC worker that takes one job and answers it with `raw`."""

    def run():
        job = queue.next_job(wait=2)
        if seen is not None:
            seen.append(job)
        if job:
            queue.finish(job["id"], raw)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    time.sleep(0.2)  # the worker is polling, as on the PC
    return thread


def test_no_worker_polling_means_offline_right_away(r):
    started = time.monotonic()
    with pytest.raises(ModelUnavailable):
        make(r, timeout=5).reply(HELLO, "And his stack?", "en")
    assert time.monotonic() - started < 1


def test_worker_gets_the_prompt_and_its_answer_reaches_the_visitor(r):
    queue, jobs = make(r), []
    worker_answers(queue, '{"reply": "Python and FastAPI.", "offer_contact": false}', jobs)
    reply = queue.reply(HELLO, "And his stack?", "pt")
    job = jobs[0]
    assert reply == ModelReply("Python and FastAPI.", False)
    assert job["system"] == "SYSTEM PROMPT" and job["schema"]["required"] == ["reply", "offer_contact"]
    assert "And his stack?" in job["prompt"] and "<page_language>pt</page_language>" in job["prompt"]


def test_worker_failure_is_offline_without_waiting_for_the_timeout(r):
    queue = make(r, timeout=5)
    worker_answers(queue, "")
    started = time.monotonic()
    with pytest.raises(ModelUnavailable):
        queue.reply(HELLO, "hi", "en")
    assert time.monotonic() - started < 2


def test_worker_that_never_answers_is_offline_after_the_timeout(r):
    queue = make(r, timeout=1)
    queue.next_job(wait=1)  # the worker polled once, then went silent
    with pytest.raises(ModelUnavailable):
        queue.reply(HELLO, "hi", "en")


def test_worker_skips_a_job_whose_visitor_already_gave_up(r):
    queue = make(r, timeout=1)
    queue.next_job(wait=1)
    with pytest.raises(ModelUnavailable):
        queue.reply(HELLO, "too late", "en")
    assert queue.next_job(wait=1) is None


def test_nothing_the_queue_writes_stays_in_redis_forever(r):
    queue = make(r)
    worker_answers(queue, json.dumps({"reply": "Hi.", "offer_contact": False}))
    queue.reply(HELLO, "hi", "en")
    queue.finish("late-job", "an answer nobody waits for")
    keys = list(r.scan_iter("chat:*"))
    assert keys and all(r.ttl(key) > 0 for key in keys)
