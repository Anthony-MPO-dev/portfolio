"""Worker queue: the ChatModel that hands each request to Anthony's PC through Redis and streams the answer back as
the worker writes it, plus the worker's side of it.

Runs on fakeredis by default; set REDIS_TEST_URL (local Redis only) to run on a real server too.
"""

import os
import threading
import time

import pytest
import redis

from app.adapters.worker_queue import WorkerQueue
from app.ports import ModelReply, ModelUnavailable
from tests.conftest import BACKENDS

HELLO = [{"role": "user", "content": "Who is he?"}, {"role": "assistant", "content": "An AI engineer."}]


def make(r, timeout=2):
    return WorkerQueue(r, system="SYSTEM PROMPT", timeout=timeout)


def ask(queue: WorkerQueue, message="hi", lang="en"):
    """Read the whole stream: the text pieces, then the final reply."""
    pieces, final = [], None
    for item in queue.stream(HELLO, message, lang):
        if isinstance(item, ModelReply):
            final = item
        else:
            pieces.append(item)
    return pieces, final


def worker_answers(queue: WorkerQueue, raw: str, seen: list | None = None, chunks=()):
    """Start a fake PC worker that takes one job, streams `chunks` and answers it with `raw`."""

    def run():
        job = queue.next_job(wait=2)
        if seen is not None:
            seen.append(job)
        if job:
            for chunk in chunks:
                queue.chunk(job["id"], chunk)
            queue.finish(job["id"], raw)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    time.sleep(0.2)  # the worker is polling, as on the PC
    return thread


def test_no_worker_polling_means_offline_right_away(r):
    started = time.monotonic()
    with pytest.raises(ModelUnavailable):
        ask(make(r, timeout=5), "And his stack?")
    assert time.monotonic() - started < 1


def test_the_answer_streams_piece_by_piece_and_ends_with_the_final_reply(r):
    queue, jobs = make(r), []
    worker_answers(queue, "Python and FastAPI.\n[[contact]]", jobs, chunks=["Python ", "and FastAPI."])
    pieces, final = ask(queue, "And his stack?", "pt")
    job = jobs[0]
    assert (pieces, final) == (["Python ", "and FastAPI."], ModelReply("Python and FastAPI.", True))
    assert job["system"] == "SYSTEM PROMPT" and "schema" not in job
    assert "And his stack?" in job["prompt"] and '"page_language": "pt"' in job["prompt"]


def test_worker_failure_is_offline_without_waiting_for_the_timeout(r):
    queue = make(r, timeout=5)
    worker_answers(queue, "")
    started = time.monotonic()
    with pytest.raises(ModelUnavailable):
        ask(queue)
    assert time.monotonic() - started < 2


def test_worker_that_never_answers_is_offline_after_the_timeout(r):
    queue = make(r, timeout=1)
    queue.next_job(wait=1)  # the worker polled once, then went silent
    with pytest.raises(ModelUnavailable):
        ask(queue)


def test_worker_skips_a_job_whose_visitor_already_gave_up(r):
    queue = make(r, timeout=1)
    queue.next_job(wait=1)
    with pytest.raises(ModelUnavailable):
        ask(queue, "too late")
    assert queue.next_job(wait=1) is None


def test_nothing_the_queue_writes_stays_in_redis_forever(r):
    queue = make(r)
    worker_answers(queue, "Hi.", chunks=["Hi."])
    ask(queue)
    queue.chunk("late-job", "a piece nobody waits for")
    queue.finish("late-job", "an answer nobody waits for")
    keys = list(r.scan_iter("chat:*"))
    assert keys and all(r.ttl(key) > 0 for key in keys)


@pytest.mark.skipif("redis" not in BACKENDS, reason="needs a real Redis: fakeredis has no socket timeout")
def test_long_waits_work_with_a_client_socket_timeout_shorter_than_the_wait():
    client = redis.Redis.from_url(os.environ["REDIS_TEST_URL"], decode_responses=True, socket_timeout=1)
    client.flushdb()
    queue = WorkerQueue(client, system="s", timeout=3, block_slice=0.5)
    assert queue.next_job(wait=3) is None
    with pytest.raises(ModelUnavailable):
        ask(queue)
    client.flushdb()


def test_presence_is_renewed_when_a_job_is_handed_out(r):
    queue, ttls = make(r), []

    def run():
        job = queue.next_job(wait=2)
        ttls.append(r.ttl("chat:worker:seen"))  # while claude runs, before the answer goes back
        queue.finish(job["id"], "Hi.")

    threading.Thread(target=run, daemon=True).start()
    time.sleep(0.2)
    r.expire("chat:worker:seen", 1)  # the long poll used up most of the presence window
    ask(queue)
    assert ttls[0] > 50


def test_images_ride_in_the_job_as_base64_png_and_texts_in_the_prompt(r):
    from app.ports import Attachment

    queue, jobs = make(r), []
    worker_answers(queue, "Two files.", jobs)
    files = [Attachment("pdf", "pdf, 1 page", text="Invoice 42"), Attachment("image", "image, 2x2", png=b"\x89PNG")]
    pieces, final = [], None
    for item in queue.stream(HELLO, "What are these?", "en", files):
        final = item if isinstance(item, ModelReply) else final
    job = jobs[0]
    assert final == ModelReply("Two files.", False)
    assert job["images"] == ["iVBORw=="] and "Invoice 42" in job["prompt"]


def test_a_job_without_images_carries_no_image_list(r):
    queue, jobs = make(r), []
    worker_answers(queue, "Hi.", jobs)
    ask(queue)
    assert "images" not in jobs[0]
