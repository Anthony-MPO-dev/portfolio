"""Worker queue: the ChatModel that runs on Anthony's PC, reached through Redis.

Responsibility: the API pushes each model request to a Redis list and streams the answer back as the worker writes
it; the worker on Anthony's PC pulls jobs and sends text pieces and the final answer through three authenticated
HTTPS routes (no port open at his home, no Redis exposed). If no worker has polled lately, or the answer doesn't
come in time, or the worker reports a failure (empty answer), or 10 jobs are already waiting, the visitor gets
"offline" through ModelUnavailable, even mid-stream. The contact line is taken out of the pieces here, so the use case
never sees the model's wire format. Jobs carry a deadline, so a worker that comes back late skips what nobody is
waiting for. Blocking reads go in slices shorter than the Redis client's socket timeout (redis-py 8 defaults to 5 s),
so a 20 s poll or a 45 s wait never trips it. Keys, all with an expiry:
- chat:jobs          pending jobs (JSON: id, system, prompt, deadline)
- chat:res:{id}      one job's stream: {"d": piece} messages, then {"end": final answer}
- chat:worker:seen   set on every poll, job handed out and answer; missing means the PC is off
Public API: WorkerQueue.stream (ChatModel), WorkerQueue.next_job, .chunk and .finish (the worker routes).
Used by: the API composition (app.main) and the worker routes.
Depends on: redis-py, app.adapters.prompt (transcript, parse_reply, without_contact), app.ports.
Tests: tests/test_worker_queue.py (fakeredis; a real local Redis when REDIS_TEST_URL is set).
"""

import base64
import json
import secrets
import time
from collections.abc import Iterator, Sequence

from redis import Redis

from app.adapters.prompt import parse_reply, transcript, without_contact
from app.ports import Attachment, Job, ModelReply, ModelUnavailable, Turn

JOBS = "chat:jobs"
SEEN = "chat:worker:seen"
SEEN_TTL = 60
MAX_JOBS = 10  # the PC answers one at a time, in seconds each: more than this waiting means it can't keep up


class WorkerQueue:
    def __init__(self, redis: Redis, system: str, timeout: int = 45, block_slice: float = 2):
        self.redis = redis
        self.system = system
        self.timeout = timeout
        self.block_slice = block_slice  # must stay below the client's socket timeout

    # API side (ChatModel)

    def stream(
        self, history: list[Turn], message: str, page_lang: str, attachments: Sequence[Attachment] = ()
    ) -> Iterator[str | ModelReply]:
        """Yield the answer's text pieces as the worker writes them, then the final ModelReply. File texts go in the
        prompt; images ride in the job as base64 PNG, which the worker sends as image blocks."""
        return without_contact(self._run(history, message, page_lang, attachments))

    def _run(
        self, history: list[Turn], message: str, page_lang: str, attachments: Sequence[Attachment]
    ) -> Iterator[str | ModelReply]:
        if not self.redis.exists(SEEN):
            raise ModelUnavailable("worker offline")
        if self.redis.llen(JOBS) >= MAX_JOBS:
            raise ModelUnavailable("queue full")
        job_id = secrets.token_hex(16)
        job = Job(id=job_id, system=self.system, prompt=transcript(history, message, page_lang, attachments),
                  deadline=time.time() + self.timeout)  # fmt: skip
        if images := [base64.b64encode(f.png).decode() for f in attachments if f.png]:
            job["images"] = images
        payload = json.dumps(job, ensure_ascii=False)
        self.redis.pipeline().rpush(JOBS, payload).expire(JOBS, 2 * self.timeout).execute()
        until = time.monotonic() + self.timeout
        while item := self._blpop(f"chat:res:{job_id}", until - time.monotonic()):
            sent = json.loads(item[1])
            if "end" in sent:
                yield parse_reply(sent["end"])
                return
            yield str(sent.get("d") or "")
        self.redis.lrem(JOBS, 1, payload)  # if it was never taken, nobody will wait for it
        raise ModelUnavailable("worker timeout")

    # worker side (the three routes)

    def next_job(self, wait: int) -> Job | None:
        """Wait up to `wait` seconds for a job nobody gave up on. None when there's nothing to do."""
        self._seen()
        until = time.monotonic() + wait
        while item := self._blpop(JOBS, until - time.monotonic()):
            job = json.loads(item[1])
            if job["deadline"] > time.time():
                self._seen()  # the poll may have used most of the window; the job can take up to `timeout`
                return job
        return None

    def chunk(self, job_id: str, text: str) -> None:
        """A piece of the answer as the worker writes it."""
        self._push(job_id, {"d": text})

    def finish(self, job_id: str, raw: str) -> None:
        """Hand the model's final answer back. An empty answer tells the API the model failed."""
        self._push(job_id, {"end": raw})

    def _push(self, job_id: str, message: dict) -> None:
        self._seen()
        key = f"chat:res:{job_id}"
        self.redis.pipeline().rpush(key, json.dumps(message, ensure_ascii=False)).expire(key, 2 * self.timeout).execute()

    def _blpop(self, key: str, seconds: float) -> tuple[str, str] | None:
        """BLPOP for up to `seconds`, in slices the client's socket timeout allows."""
        until = time.monotonic() + seconds
        while (left := until - time.monotonic()) > 0:
            slice_ = max(round(min(left, self.block_slice), 2), 0.01)  # BLPOP with timeout 0 would block forever
            if item := self.redis.blpop([key], timeout=slice_):
                return item
        return None

    def _seen(self) -> None:
        self.redis.set(SEEN, 1, ex=SEEN_TTL)
