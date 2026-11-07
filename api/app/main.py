"""Composition: wire the real adapters from the environment and build the API.

Responsibility: read the settings, refuse to start when a secret is missing or too short (there are no default
secrets), pick the model engine, and hand the use cases their adapters. Engines: "worker" (Anthony's PC, the
default). The Anthropic API engine is planned and refused until it exists.
Settings: REDIS_URL, DATABASE_URL, LEAD_WEBHOOK_URL, WORKER_TOKEN (32+ chars), IP_HMAC_KEY (32+ chars),
CONTACT_WHATSAPP; optional SITE_ORIGIN, MODEL_ENGINE, MODEL_TIMEOUT (seconds), FACTS_PATH.
Public API: build (pure: no network), app (the uvicorn factory: also creates the tables), ConfigError.
Run: uvicorn app.main:app --factory
Used by: the Docker image.
Depends on: every adapter, app.http, app.prompt, the use cases.
Tests: tests/test_main.py.
"""

import logging
import os
import secrets
from collections.abc import Mapping
from pathlib import Path

import psycopg
import redis
from fastapi import FastAPI

from app.adapters.lead_alert import N8nAlert, SaveThenAlert
from app.adapters.postgres import PostgresLeadSink, PostgresQuestionLog, ensure_schema
from app.adapters.redis_store import RedisStore
from app.adapters.worker_queue import WorkerQueue
from app.http import create_app
from app.prompt import system_prompt
from app.services.chat import ChatService
from app.services.lead import LeadService

log = logging.getLogger(__name__)
REQUIRED = ("REDIS_URL", "DATABASE_URL", "LEAD_WEBHOOK_URL", "WORKER_TOKEN", "IP_HMAC_KEY", "CONTACT_WHATSAPP")
MIN_SECRET = 32
DEFAULT_FACTS = Path(__file__).resolve().parents[2] / "knowledge" / "facts.md"


class ConfigError(RuntimeError):
    """The API can't start with these settings."""


def build(env: Mapping[str, str]) -> FastAPI:
    missing = [key for key in REQUIRED if not env.get(key)]
    if missing:
        raise ConfigError(f"missing settings: {', '.join(missing)}")
    short = [key for key in ("WORKER_TOKEN", "IP_HMAC_KEY") if len(env[key]) < MIN_SECRET]
    if short:
        raise ConfigError(f"{', '.join(short)} must have at least {MIN_SECRET} characters")
    engine = env.get("MODEL_ENGINE", "worker")
    if engine != "worker":
        raise ConfigError(f"MODEL_ENGINE={engine!r} is not available; use 'worker'")

    facts = Path(env.get("FACTS_PATH") or DEFAULT_FACTS).read_text(encoding="utf-8")
    r = redis.Redis.from_url(env["REDIS_URL"], decode_responses=True)
    store = RedisStore(r)
    queue = WorkerQueue(r, system_prompt(facts), timeout=int(env.get("MODEL_TIMEOUT", "45")))
    db = env["DATABASE_URL"]
    chat = ChatService(queue, store, PostgresQuestionLog(db), new_session_id=lambda: secrets.token_urlsafe(32))
    sink = SaveThenAlert(PostgresLeadSink(db), N8nAlert(env["LEAD_WEBHOOK_URL"]))
    lead = LeadService(sink, store, whatsapp=env["CONTACT_WHATSAPP"])
    return create_app(
        chat=chat,
        lead=lead,
        worker=queue,
        worker_token=env["WORKER_TOKEN"],
        ip_key=env["IP_HMAC_KEY"].encode(),
        origin=env.get("SITE_ORIGIN", "https://anthonymuniz.dev"),
    )


def app() -> FastAPI:
    api = build(os.environ)
    try:
        ensure_schema(os.environ["DATABASE_URL"])
    except psycopg.Error:
        log.warning("Postgres unreachable at startup: leads and the question log are down until it's back")
    return api
