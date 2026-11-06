"""Redis session store and counters.

Responsibility: implement SessionStore and FormCounter on Redis with the keys from the phase 2 decisions. Every key
it writes has an expiry, so nothing about a visitor stays forever:
- chat:m:{sid}            turn counter, 24 h absolute (proof that the server created the id)
- chat:h:{sid}            last 20 messages as JSON, 2 h sliding
- chat:lock:{sid}         one answer at a time, 90 s (longer than the model timeout)
- chat:rl:{key}:h|d:{t}   messages per client per hour and per day (the key is an HMAC of the IP, never the IP)
- chat:g:{day}            messages for the whole site today
- chat:form:{key}:{day}   valid contact forms per client today
Windows are fixed and in UTC.
Public API: RedisStore.
Used by: the API composition (app.main).
Depends on: redis-py (any client with decode_responses or bytes), app.ports.Turn.
Tests: tests/test_redis_store.py (fakeredis; a real local Redis when REDIS_TEST_URL is set).
"""

import json
from collections.abc import Callable
from datetime import UTC, datetime

from redis import Redis

from app.ports import Turn

HOUR = 3600
DAY = 86400


class RedisStore:
    def __init__(
        self,
        redis: Redis,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        history_size: int = 20,
        idle_ttl: int = 2 * HOUR,
        session_ttl: int = DAY,
        lock_ttl: int = 90,
    ):
        self.r = redis
        self.now = now
        self.history_size = history_size
        self.idle_ttl = idle_ttl
        self.session_ttl = session_ttl
        self.lock_ttl = lock_ttl

    # sessions

    def session_exists(self, sid: str) -> bool:
        return bool(self.r.exists(f"chat:m:{sid}"))

    def create_session(self, sid: str) -> None:
        self.r.set(f"chat:m:{sid}", 0, ex=self.session_ttl, nx=True)

    def count_turn(self, sid: str) -> int:
        key = f"chat:m:{sid}"
        turns, ttl = self.r.pipeline().incr(key).ttl(key).execute()
        if ttl == -1:  # the session expired between the check and the INCR, which recreated it without expiry
            self.r.expire(key, self.session_ttl)
        return turns

    def acquire_lock(self, sid: str) -> bool:
        return bool(self.r.set(f"chat:lock:{sid}", 1, ex=self.lock_ttl, nx=True))

    def release_lock(self, sid: str) -> None:
        self.r.delete(f"chat:lock:{sid}")

    def history(self, sid: str) -> list[Turn]:
        return [json.loads(item) for item in self.r.lrange(f"chat:h:{sid}", 0, -1)]

    def append_turn(self, sid: str, question: str, answer: str) -> None:
        key = f"chat:h:{sid}"
        turns = ({"role": "user", "content": question}, {"role": "assistant", "content": answer})
        pipe = self.r.pipeline()
        pipe.rpush(key, *(json.dumps(t, ensure_ascii=False) for t in turns))
        pipe.ltrim(key, -self.history_size, -1)
        pipe.expire(key, self.idle_ttl)
        pipe.execute()

    # counters

    def hit_ip(self, client_key: str) -> tuple[int, int]:
        t = self.now()
        hour, day = self._count(
            (f"chat:rl:{client_key}:h:{t:%Y%m%d%H}", 2 * HOUR), (f"chat:rl:{client_key}:d:{t:%Y%m%d}", 2 * DAY)
        )
        return hour, day

    def hit_global(self) -> int:
        return self._count((f"chat:g:{self.now():%Y%m%d}", 2 * DAY))[0]

    def hit_form(self, client_key: str) -> int:
        return self._count((f"chat:form:{client_key}:{self.now():%Y%m%d}", 2 * DAY))[0]

    def _count(self, *windows: tuple[str, int]) -> list[int]:
        pipe = self.r.pipeline()
        for key, ttl in windows:
            pipe.incr(key).expire(key, ttl)
        return pipe.execute()[::2]
