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


@pytest.fixture
def env(tmp_path):
    facts = tmp_path / "facts.md"
    facts.write_text("# Anthony Muniz: public facts", encoding="utf-8")
    return {**ENV, "FACTS_PATH": str(facts)}


def test_complete_settings_build_the_api(env):
    paths = {route.path for route in build(env).routes}
    assert isinstance(build(env), FastAPI) and {"/api/chat", "/api/lead", "/api/worker/next"} <= paths


def test_every_missing_secret_is_named_at_startup(env):
    with pytest.raises(ConfigError, match="WORKER_TOKEN.*CONTACT_WHATSAPP"):
        build({k: v for k, v in env.items() if k not in ("WORKER_TOKEN", "CONTACT_WHATSAPP")})


@pytest.mark.parametrize("key", ["WORKER_TOKEN", "IP_HMAC_KEY"])
def test_short_secrets_are_refused(env, key):
    with pytest.raises(ConfigError, match=key):
        build({**env, key: "short"})


def test_engine_that_is_not_built_yet_is_refused(env):
    with pytest.raises(ConfigError, match="MODEL_ENGINE"):
        build({**env, "MODEL_ENGINE": "anthropic"})
