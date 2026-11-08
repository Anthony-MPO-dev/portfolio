"""Redis session store and counters: the SessionStore and FormCounter contracts, plus the keys' lifetimes.

Runs on fakeredis by default. Set REDIS_TEST_URL (local Redis only, the tests flush it) to run on a real server too.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.adapters.redis_store import RedisAnswerCache, RedisStore
from app.ports import ModelReply


class Clock:
    def __init__(self):
        self.now = datetime(2026, 11, 6, 13, 30, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta) -> None:
        self.now += timedelta(**delta)


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def store(r, clock):
    return RedisStore(r, now=clock)


def test_only_sessions_the_server_created_exist(store):
    store.create_session("sid-1")
    assert (store.session_exists("sid-1"), store.session_exists("forged")) == (True, False)


def test_saved_exchanges_are_counted_and_the_session_keeps_its_24_hour_limit(store, r):
    store.create_session("sid-1")
    before = store.turns("sid-1")
    store.append_turn("sid-1", "q1", "a1")
    store.append_turn("sid-1", "q2", "a2")
    assert (before, store.turns("sid-1"), 0 < r.ttl("chat:m:sid-1") <= 86400) == (0, 2, True)


def test_saving_on_a_session_that_just_expired_never_creates_a_key_without_expiry(store, r):
    store.append_turn("sid-gone", "q", "a")
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
    store.acquire_lock("sid-1")
    store.append_turn("sid-1", "q", "a")
    store.hit_ip("ip-a")
    store.hit_global()
    store.hit_form("ip-a")
    keys = list(r.scan_iter("chat:*"))
    assert len(keys) == 7 and all(r.ttl(key) > 0 for key in keys)


def test_erasing_a_session_removes_everything_stored_about_it(store, r):
    store.create_session("sid-1")
    store.acquire_lock("sid-1")
    store.append_turn("sid-1", "My name is Jane", "Hi Jane.")
    store.delete_session("sid-1")
    assert (store.session_exists("sid-1"), store.history("sid-1"), list(r.scan_iter("chat:*sid-1"))) == (False, [], [])


def test_the_chat_off_key_switches_the_chat_off(store, r):
    assert store.switched_off() is False
    r.set("chat:off", 1)
    assert store.switched_off() is True


def test_the_answer_cache_keeps_a_clean_answer_for_a_day_under_a_hash_of_the_question(r):
    cache = RedisAnswerCache(r, version="v1")
    cache.put("en", "is he open to remote roles", ModelReply("Yes.", offer_contact=True))
    assert cache.get("en", "is he open to remote roles") == ModelReply("Yes.", offer_contact=True)
    (key,) = r.keys("chat:c:*")
    assert "remote" not in key and 0 < r.ttl(key) <= 86400


def test_the_answer_cache_misses_on_another_language_or_prompt_version(r):
    RedisAnswerCache(r, version="v1").put("en", "q", ModelReply("A", offer_contact=False))
    assert RedisAnswerCache(r, version="v1").get("pt", "q") is None
    assert RedisAnswerCache(r, version="v2").get("en", "q") is None
