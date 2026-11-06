"""Worker queue: the ChatModel that runs on Anthony's PC, reached through Redis.

Responsibility: the API pushes each model request to a Redis list and waits for the answer; the worker on Anthony's
PC pulls jobs through two authenticated HTTPS routes (no port open at his home, no Redis exposed). If no worker has
polled lately, or the answer doesn't come in time, or the worker reports a failure (empty answer), the visitor gets
"offline" through ModelUnavailable. Jobs carry a deadline, so a worker that comes back late skips what nobody is
waiting for. Keys, all with an expiry:
- chat:jobs          pending jobs (JSON: id, system, prompt, schema, deadline)
- chat:res:{id}      the raw answer for one job
- chat:worker:seen   set on every poll and answer; missing means the PC is off
Public API: WorkerQueue.reply (ChatModel), WorkerQueue.next_job and WorkerQueue.finish (the worker routes).
Used by: the API composition (app.main) and the worker routes.
Depends on: redis-py, app.prompt (transcript, parse_reply, REPLY_SCHEMA), app.ports.
Tests: tests/test_worker_queue.py (fakeredis; a real local Redis when REDIS_TEST_URL is set).
"""

import json
import secrets
import time

from redis import Redis

from app.ports import ModelReply, ModelUnavailable, Turn
from app.prompt import REPLY_SCHEMA, parse_reply, transcript

JOBS = "chat:jobs"
SEEN = "chat:worker:seen"


class WorkerQueue:
    def __init__(self, redis: Redis, system: str, timeout: int = 45, seen_ttl: int = 60):
        self.r = redis
        self.system = system
        self.timeout = timeout
        self.seen_ttl = seen_ttl

    # API side (ChatModel)

    def reply(self, history: list[Turn], message: str, page_lang: str) -> ModelReply:
        if not self.r.exists(SEEN):
            raise ModelUnavailable("worker offline")
        job_id = secrets.token_hex(16)
        payload = json.dumps(
            {
                "id": job_id,
                "system": self.system,
                "prompt": transcript(history, message, page_lang),
                "schema": REPLY_SCHEMA,
                "deadline": time.time() + self.timeout,
            },
            ensure_ascii=False,
        )
        self.r.pipeline().rpush(JOBS, payload).expire(JOBS, 2 * self.timeout).execute()
        answer = self.r.blpop([f"chat:res:{job_id}"], timeout=self.timeout)
        if answer is None:
            self.r.lrem(JOBS, 1, payload)  # not taken yet: nobody will wait for it
            raise ModelUnavailable("worker timeout")
        return parse_reply(answer[1])

    # worker side (the two routes)

    def next_job(self, wait: int) -> dict | None:
        """Wait up to `wait` seconds for a job nobody gave up on. None when there's nothing to do."""
        self._seen()
        while item := self.r.blpop([JOBS], timeout=wait):
            job = json.loads(item[1])
            if job["deadline"] > time.time():
                return job
        return None

    def finish(self, job_id: str, raw: str) -> None:
        """Hand the model's raw answer back. An empty answer tells the API the model failed."""
        self._seen()
        key = f"chat:res:{job_id}"
        self.r.pipeline().rpush(key, raw).expire(key, 2 * self.timeout).execute()

    def _seen(self) -> None:
        self.r.set(SEEN, 1, ex=self.seen_ttl)
