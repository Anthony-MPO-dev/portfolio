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
HISTORY_SIZE = 20  # messages
IDLE_TTL = 2 * HOUR
SESSION_TTL = DAY
LOCK_TTL = 90  # longer than the model timeout


class RedisStore:
    def __init__(self, redis: Redis, now: Callable[[], datetime] = lambda: datetime.now(UTC)):
        self.redis = redis
        self.now = now

    # sessions

    def session_exists(self, sid: str) -> bool:
        return bool(self.redis.exists(f"chat:m:{sid}"))

    def create_session(self, sid: str) -> None:
        self.redis.set(f"chat:m:{sid}", 0, ex=SESSION_TTL, nx=True)

    def turns(self, sid: str) -> int:
        return int(self.redis.get(f"chat:m:{sid}") or 0)

    def acquire_lock(self, sid: str) -> bool:
        return bool(self.redis.set(f"chat:lock:{sid}", 1, ex=LOCK_TTL, nx=True))

    def release_lock(self, sid: str) -> None:
        self.redis.delete(f"chat:lock:{sid}")

    def history(self, sid: str) -> list[Turn]:
        return [json.loads(item) for item in self.redis.lrange(f"chat:h:{sid}", 0, -1)]

    def append_turn(self, sid: str, question: str, answer: str) -> None:
        key, counter = f"chat:h:{sid}", f"chat:m:{sid}"
        turns = ({"role": "user", "content": question}, {"role": "assistant", "content": answer})
        pipe = self.redis.pipeline()
        pipe.rpush(key, *(json.dumps(t, ensure_ascii=False) for t in turns))
        pipe.ltrim(key, -HISTORY_SIZE, -1)
        pipe.expire(key, IDLE_TTL)
        pipe.incr(counter).ttl(counter)
        if pipe.execute()[-1] == -1:  # the session expired just before, and INCR recreated it without expiry
            self.redis.expire(counter, SESSION_TTL)

    def delete_session(self, sid: str) -> None:
        self.redis.delete(f"chat:m:{sid}", f"chat:h:{sid}", f"chat:lock:{sid}")

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
        pipe = self.redis.pipeline()
        for key, ttl in windows:
            pipe.incr(key).expire(key, ttl)
        return pipe.execute()[::2]
