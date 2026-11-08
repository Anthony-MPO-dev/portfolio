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
    monkeypatch.setattr("app.main.N8nSecurityAlert", lambda url, r: made.append(url) or (lambda reason: None))
    build(env, FACTS)
    assert made == [env["LEAD_WEBHOOK_URL"]]
