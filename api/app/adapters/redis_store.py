"""Redis session store and counters.

Responsibility: implement SessionStore, FormCounter and AnswerCache on Redis with the keys from the phase 2
decisions. Every key it writes has an expiry, so nothing about a visitor stays forever:
- chat:m:{sid}            turn counter, 24 h absolute (proof that the server created the id)
- chat:h:{sid}            last 20 messages as JSON, 2 h sliding
- chat:lock:{sid}         one answer at a time, 90 s (longer than the model timeout)
- chat:rl:{key}:h|d:{t}   messages per client per hour and per day (the key is an HMAC of the IP, never the IP)
- chat:g:{day}            messages for the whole site today
- chat:form:{key}:{day}   valid contact forms per client today
- chat:c:{v}:{lang}:{hash}  a clean answer to a first question, 24 h (v: prompt version; hash: SHA-256 of the
                          normalized question, so the key never holds the visitor's words)
- chat:a:{sid}:{id}        a converted file (never the original), 30 min, dropped when its answer ends
- chat:ac:{sid}           files uploaded in the session, 24 h
- chat:off                the operator's off switch, set by hand (no TTL)
- chat:attachments:off    the operator's switch for uploads only, set by hand (no TTL)
Windows are fixed and in UTC.
Public API: RedisStore, RedisAnswerCache.
Used by: the API composition (app.main).
Depends on: redis-py (any client with decode_responses or bytes), app.ports (Turn, ModelReply).
Tests: tests/test_redis_store.py (fakeredis; a real local Redis when REDIS_TEST_URL is set).
"""

import base64
import hashlib
import json
import secrets
from collections.abc import Callable, Sequence
from datetime import UTC, datetime

from redis import Redis

from app.ports import Attachment, ModelReply, Turn

HOUR = 3600
DAY = 86400
HISTORY_SIZE = 20  # messages
IDLE_TTL = 2 * HOUR
SESSION_TTL = DAY
LOCK_TTL = 90  # longer than the model timeout
CACHE_TTL = DAY
FILE_TTL = 30 * 60  # a file waits at most this long for its answer


class RedisStore:
    def __init__(self, redis: Redis, now: Callable[[], datetime] = lambda: datetime.now(UTC)):
        self.redis = redis
        self.now = now

    # sessions

    def switched_off(self) -> bool:
        return bool(self.redis.exists("chat:off"))

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

    def attachments_off(self) -> bool:
        return bool(self.redis.exists("chat:attachments:off"))

    def attachment_count(self, sid: str) -> int:
        return int(self.redis.get(f"chat:ac:{sid}") or 0)

    def save_attachment(self, sid: str, attachment: Attachment) -> str:
        aid = secrets.token_hex(8)
        png = base64.b64encode(attachment.png).decode() if attachment.png else None
        value = json.dumps({"kind": attachment.kind, "summary": attachment.summary, "text": attachment.text, "png": png})
        pipe = self.redis.pipeline()
        pipe.set(f"chat:a:{sid}:{aid}", value, ex=FILE_TTL).incr(f"chat:ac:{sid}").expire(f"chat:ac:{sid}", SESSION_TTL)
        pipe.execute()
        return aid

    def attachments(self, sid: str, ids: Sequence[str]) -> list[Attachment] | None:
        pipe = self.redis.pipeline()
        for aid in ids:
            pipe.get(f"chat:a:{sid}:{aid}")
        found = pipe.execute()
        if not all(found):
            return None
        files = [json.loads(raw) for raw in found]
        return [Attachment(f["kind"], f["summary"], f["text"], base64.b64decode(f["png"]) if f["png"] else None)
                for f in files]  # fmt: skip

    def drop_attachments(self, sid: str, ids: Sequence[str]) -> None:
        self.redis.delete(*(f"chat:a:{sid}:{aid}" for aid in ids))

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


class RedisAnswerCache:
    def __init__(self, redis: Redis, version: str):
        self.redis, self.version = redis, version

    def get(self, lang: str, question: str) -> ModelReply | None:
        raw = self.redis.get(self._key(lang, question))
        return ModelReply(**json.loads(raw)) if raw else None

    def put(self, lang: str, question: str, reply: ModelReply) -> None:
        value = json.dumps({"text": reply.text, "offer_contact": reply.offer_contact}, ensure_ascii=False)
        self.redis.set(self._key(lang, question), value, ex=CACHE_TTL)

    def _key(self, lang: str, question: str) -> str:
        return f"chat:c:{self.version}:{lang}:{hashlib.sha256(question.encode()).hexdigest()}"
