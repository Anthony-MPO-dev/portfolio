"""Worker queue: the ChatModel that runs on Anthony's PC, reached through Redis.

Responsibility: the API pushes each model request to a Redis list and waits for the answer; the worker on Anthony's
PC pulls jobs through two authenticated HTTPS routes (no port open at his home, no Redis exposed). If no worker has
polled lately, or the answer doesn't come in time, or the worker reports a failure (empty answer), the visitor gets
"offline" through ModelUnavailable. Jobs carry a deadline, so a worker that comes back late skips what nobody is
waiting for. Blocking reads go in slices shorter than the Redis client's socket timeout (redis-py 8 defaults to 5 s),
so a 20 s poll or a 45 s wait never trips it. Keys, all with an expiry:
- chat:jobs          pending jobs (JSON: id, system, prompt, schema, deadline)
- chat:res:{id}      the raw answer for one job
- chat:worker:seen   set on every poll, job handed out and answer; missing means the PC is off
Public API: WorkerQueue.reply (ChatModel), WorkerQueue.next_job and WorkerQueue.finish (the worker routes).
Used by: the API composition (app.main) and the worker routes.
Depends on: redis-py, app.adapters.prompt (transcript, parse_reply, REPLY_SCHEMA), app.ports.
Tests: tests/test_worker_queue.py (fakeredis; a real local Redis when REDIS_TEST_URL is set).
"""

import json
import secrets
import time

from redis import Redis

from app.adapters.prompt import REPLY_SCHEMA, parse_reply, transcript
from app.ports import Job, ModelReply, ModelUnavailable, Turn

JOBS = "chat:jobs"
SEEN = "chat:worker:seen"
SEEN_TTL = 60


class WorkerQueue:
    def __init__(self, redis: Redis, system: str, timeout: int = 45, block_slice: float = 2):
        self.redis = redis
        self.system = system
        self.timeout = timeout
        self.block_slice = block_slice  # must stay below the client's socket timeout

    # API side (ChatModel)

    def reply(self, history: list[Turn], message: str, page_lang: str) -> ModelReply:
        if not self.redis.exists(SEEN):
            raise ModelUnavailable("worker offline")
        job_id = secrets.token_hex(16)
        job = Job(
            id=job_id,
            system=self.system,
            prompt=transcript(history, message, page_lang),
            schema=REPLY_SCHEMA,
            deadline=time.time() + self.timeout,
        )
        payload = json.dumps(job, ensure_ascii=False)
        self.redis.pipeline().rpush(JOBS, payload).expire(JOBS, 2 * self.timeout).execute()
        answer = self._blpop(f"chat:res:{job_id}", self.timeout)
        if answer is None:
            self.redis.lrem(JOBS, 1, payload)  # not taken yet: nobody will wait for it
            raise ModelUnavailable("worker timeout")
        return parse_reply(answer[1])

    # worker side (the two routes)

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

    def finish(self, job_id: str, raw: str) -> None:
        """Hand the model's raw answer back. An empty answer tells the API the model failed."""
        self._seen()
        key = f"chat:res:{job_id}"
        self.redis.pipeline().rpush(key, raw).expire(key, 2 * self.timeout).execute()

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
