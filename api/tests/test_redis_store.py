"""Redis session store and counters: the SessionStore and FormCounter contracts, plus the keys' lifetimes.

Runs on fakeredis by default. Set REDIS_TEST_URL (local Redis only, the tests flush it) to run on a real server too.
"""

import os
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

import fakeredis
import pytest
import redis

from app.adapters.redis_store import RedisStore

BACKENDS = ["fakeredis"] + (["redis"] if os.environ.get("REDIS_TEST_URL") else [])


class Clock:
    def __init__(self):
        self.now = datetime(2026, 11, 6, 13, 30, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta) -> None:
        self.now += timedelta(**delta)


@pytest.fixture(params=BACKENDS)
def r(request):
    if request.param == "fakeredis":
        client = fakeredis.FakeRedis(decode_responses=True)
    else:
        url = os.environ["REDIS_TEST_URL"]
        assert urlparse(url).hostname in ("localhost", "127.0.0.1"), "these tests flush the database"
        client = redis.Redis.from_url(url, decode_responses=True)
    client.flushdb()
    yield client
    client.flushdb()


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def store(r, clock):
    return RedisStore(r, now=clock)


def test_only_sessions_the_server_created_exist(store):
    store.create_session("sid-1")
    assert (store.session_exists("sid-1"), store.session_exists("forged")) == (True, False)


def test_turns_are_counted_and_the_session_keeps_its_24_hour_limit(store, r):
    store.create_session("sid-1")
    counts = [store.count_turn("sid-1") for _ in range(2)]
    assert (counts, 0 < r.ttl("chat:m:sid-1") <= 86400) == ([1, 2], True)


def test_counting_a_turn_on_a_session_that_just_expired_never_creates_a_key_without_expiry(store, r):
    store.count_turn("sid-gone")
    assert r.ttl("chat:m:sid-gone") > 0


def test_history_returns_the_turns_in_order(store):
    store.append_turn("sid-1", "Quem é ele?", "Um engenheiro de IA.")
    store.append_turn("sid-1", "Stack?", "Python.")
    assert store.history("sid-1") == [
        {"role": "user", "content": "Quem é ele?"},
        {"role": "assistant", "content": "Um engenheiro de IA."},
        {"role": "user", "content": "Stack?"},
        {"role": "assistant", "content": "Python."},
    ]


def test_history_keeps_only_the_last_20_messages(store):
    for n in range(1, 12):
        store.append_turn("sid-1", f"q{n}", f"a{n}")
    history = store.history("sid-1")
    assert (len(history), history[0]["content"]) == (20, "q2")


def test_history_expires_after_2_hours_without_use(store, r):
    store.append_turn("sid-1", "q", "a")
    assert 7000 < r.ttl("chat:h:sid-1") <= 7200


def test_unknown_session_has_empty_history(store):
    assert store.history("sid-x") == []


def test_one_answer_at_a_time_per_session(store):
    taken = [store.acquire_lock("sid-1"), store.acquire_lock("sid-1")]
    store.release_lock("sid-1")
    assert (taken, store.acquire_lock("sid-1")) == ([True, False], True)


def test_a_crashed_answer_does_not_hold_the_lock_forever(store, r):
    store.acquire_lock("sid-1")
    assert 0 < r.ttl("chat:lock:sid-1") <= 90


def test_ip_counts_reset_each_hour_and_each_day(store, clock):
    store.hit_ip("ip-a")
    second = store.hit_ip("ip-a")
    clock.advance(hours=1)
    next_hour = store.hit_ip("ip-a")
    clock.advance(days=1)
    assert (second, next_hour, store.hit_ip("ip-a")) == ((2, 2), (1, 3), (1, 1))


def test_ip_counts_are_per_client(store):
    store.hit_ip("ip-a")
    assert store.hit_ip("ip-b") == (1, 1)


def test_global_count_resets_each_day(store, clock):
    store.hit_global()
    second = store.hit_global()
    clock.advance(days=1)
    assert (second, store.hit_global()) == (2, 1)


def test_form_count_is_per_client_per_day(store, clock):
    store.hit_form("ip-a")
    second = store.hit_form("ip-a")
    other = store.hit_form("ip-b")
    clock.advance(days=1)
    assert (second, other, store.hit_form("ip-a")) == (2, 1, 1)


def test_nothing_the_chat_writes_stays_in_redis_forever(store, r):
    store.create_session("sid-1")
    store.count_turn("sid-1")
    store.acquire_lock("sid-1")
    store.append_turn("sid-1", "q", "a")
    store.hit_ip("ip-a")
    store.hit_global()
    store.hit_form("ip-a")
    keys = list(r.scan_iter("chat:*"))
    assert len(keys) == 7 and all(r.ttl(key) > 0 for key in keys)
