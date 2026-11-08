"""Composition: the API starts only with every secret set, and never with a default one."""

import pytest
from fastapi import FastAPI

from app.main import ConfigError, build

ENV = {
    "REDIS_URL": "redis://localhost:6379/0",
    "DATABASE_URL": "postgresql://portfolio:x@localhost/portfolio",
    "LEAD_WEBHOOK_URL": "https://n8n.example/webhook/lead",
    "WORKER_TOKEN": "t" * 32,
    "IP_HMAC_KEY": "k" * 32,
    "CONTACT_WHATSAPP": "+00 0000",
}


FACTS = "# Anthony Muniz: public facts"


@pytest.fixture
def env():
    return dict(ENV)


def test_complete_settings_build_the_api(env):
    paths = {route.path for route in build(env, FACTS).routes}
    assert isinstance(build(env, FACTS), FastAPI) and {"/api/chat", "/api/lead", "/api/worker/next"} <= paths


def test_every_missing_secret_is_named_at_startup(env):
    with pytest.raises(ConfigError, match="WORKER_TOKEN.*CONTACT_WHATSAPP"):
        build({k: v for k, v in env.items() if k not in ("WORKER_TOKEN", "CONTACT_WHATSAPP")}, FACTS)


@pytest.mark.parametrize("key", ["WORKER_TOKEN", "IP_HMAC_KEY"])
def test_short_secrets_are_refused(env, key):
    with pytest.raises(ConfigError, match=key):
        build({**env, key: "short"}, FACTS)


def test_engine_that_is_not_built_yet_is_refused(env):
    with pytest.raises(ConfigError, match="MODEL_ENGINE"):
        build({**env, "MODEL_ENGINE": "anthropic"}, FACTS)


def test_each_process_plants_its_own_canary_in_the_system_prompt(env, monkeypatch):
    seen = []
    monkeypatch.setattr("app.main.WorkerQueue", lambda r, system, timeout: seen.append(system))
    build(env, FACTS)
    build(env, FACTS)
    codes = [s.split("Internal reference code: ")[1].split(".")[0] for s in seen]
    assert len(codes) == 2 and codes[0] != codes[1] and len(codes[0]) >= 16


def test_security_alerts_go_to_the_lead_webhook(env, monkeypatch):
    made = []
    monkeypatch.setattr("app.main.N8nSecurityAlert", lambda url, r, post: made.append(url) or (lambda reason: None))
    build(env, FACTS)
    assert made == [env["LEAD_WEBHOOK_URL"]]


def test_redis_calls_time_out_and_the_queue_waits_on_its_own_connection(env, monkeypatch):
    import redis as redis_lib

    opened = []
    real = redis_lib.Redis.from_url
    monkeypatch.setattr(redis_lib.Redis, "from_url", lambda url, **kw: opened.append(kw) or real(url, **kw))
    build(env, FACTS)
    quick, waiting = sorted(opened, key=lambda kw: kw["socket_timeout"])
    assert quick["socket_timeout"] <= 5 and quick["socket_connect_timeout"] <= 5
    assert waiting["socket_timeout"] > 45  # longer than the worker's longest wait, or the wait itself would time out


def test_both_alerts_share_one_pooled_poster(env, monkeypatch):
    posters = []
    monkeypatch.setattr("app.main.N8nAlert", lambda url, post: posters.append(post))
    monkeypatch.setattr("app.main.N8nSecurityAlert", lambda url, r, post: posters.append(post) or (lambda reason: None))
    build(env, FACTS)
    assert len(posters) == 2 and posters[0] is posters[1]


def test_the_answer_cache_follows_the_prompt_and_not_the_canary(env, monkeypatch):
    versions = []
    monkeypatch.setattr("app.main.RedisAnswerCache", lambda r, version: versions.append(version))
    build(env, FACTS)
    build(env, FACTS)  # a new canary on each start, but the same facts and rules: the cache survives a restart
    build(env, FACTS + "\n- a new fact")
    assert versions[0] == versions[1] != versions[2]


def test_uploads_are_converted_in_the_isolated_child_process(env, monkeypatch):
    from app.attachment_sandbox import convert_isolated

    made = []
    monkeypatch.setattr("app.main.ChatService", lambda *a, **kw: made.append(kw) or object())
    monkeypatch.setattr("app.main.create_app", lambda **kw: FastAPI())
    build(env, FACTS)
    assert made[0]["convert"] is convert_isolated
