"""Shared fixtures: a Redis client per test (fakeredis, plus a real local Redis when REDIS_TEST_URL is set)."""

import os
from urllib.parse import urlparse

import fakeredis
import pytest
import redis

BACKENDS = ["fakeredis"] + (["redis"] if os.environ.get("REDIS_TEST_URL") else [])


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
