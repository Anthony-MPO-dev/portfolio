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


def test_unknown_engine_is_refused(env):
    with pytest.raises(ConfigError, match="MODEL_ENGINE"):
        build({**env, "MODEL_ENGINE": "openai"}, FACTS)


def test_anthropic_engine_needs_its_key_but_not_the_worker_token(env):
    env = {k: v for k, v in env.items() if k != "WORKER_TOKEN"} | {"MODEL_ENGINE": "anthropic"}
    with pytest.raises(ConfigError, match="ANTHROPIC_API_KEY"):
        build(env, FACTS)
    paths = {route.path for route in build({**env, "ANTHROPIC_API_KEY": "sk-test"}, FACTS).routes}
    assert "/api/chat" in paths and not any(p.startswith("/api/worker") for p in paths)
