"""Composition: wire the real adapters from the environment and build the API.

Responsibility: read the settings, refuse to start when a secret is missing or too short (there are no default
secrets), pick the model engine, plant a fresh canary in the system prompt on every start, and hand the use cases
their adapters, with the output guard bound to that canary. Engines (MODEL_ENGINE): "worker" (the isolated chat
worker, the default; needs WORKER_TOKEN, 32+ chars) or "anthropic" (the API, the author's choice of 2026-11-07; needs
ANTHROPIC_API_KEY from his personal account with a spending cap, optional ANTHROPIC_MODEL, default claude-haiku-5-5;
no worker routes).
Settings: REDIS_URL, DATABASE_URL, LEAD_WEBHOOK_URL, IP_HMAC_KEY (32+ chars), CONTACT_WHATSAPP, plus the engine's;
optional SITE_ORIGIN, MODEL_TIMEOUT (seconds), FACTS_PATH.
Redis user for REDIS_URL (checked against Redis 8 on 2026-11-06; database 0, add +select for another index):
  ACL SETUSER <user> on ><password> ~chat:* resetchannels -@all +exists +set +get +incr +incrby +ttl +expire
  +lrange +rpush +ltrim +lrem +blpop +del +multi +exec +hello +client|setinfo
Public API: build (pure: no network, no disk), app (the uvicorn factory: reads the facts, creates the tables,
starts the retention purge), ConfigError.
Run: uvicorn app.main:app --factory
Used by: the Docker image.
Depends on: every adapter, app.http, the use cases.
Tests: tests/test_main.py.
"""

import logging
import os
import secrets
import threading
import time
from collections.abc import Mapping
from functools import partial
from pathlib import Path

import anthropic
import psycopg
import redis
from fastapi import FastAPI

from app.adapters.anthropic_model import AnthropicModel
from app.adapters.lead_alert import N8nAlert, SaveThenAlert
from app.adapters.postgres import PostgresLeadSink, PostgresQuestionLog, ensure_schema, purge_expired
from app.adapters.prompt import system_prompt
from app.adapters.redis_store import RedisStore
from app.adapters.worker_queue import WorkerQueue
from app.http import create_app
from app.output_guard import check
from app.services.chat import ChatService
from app.services.lead import LeadService

log = logging.getLogger(__name__)
REQUIRED = ("REDIS_URL", "DATABASE_URL", "LEAD_WEBHOOK_URL", "IP_HMAC_KEY", "CONTACT_WHATSAPP")
ENGINES = {"worker": ("WORKER_TOKEN",), "anthropic": ("ANTHROPIC_API_KEY",)}  # engine: the settings it needs
MIN_SECRET = 32
PURGE_EVERY = 6 * 3600  # seconds
DEFAULT_FACTS = Path(__file__).resolve().parents[2] / "knowledge" / "facts.md"


class ConfigError(RuntimeError):
    """The API can't start with these settings."""


def build(env: Mapping[str, str], facts: str) -> FastAPI:
    engine = env.get("MODEL_ENGINE", "worker")
    if engine not in ENGINES:
        raise ConfigError(f"MODEL_ENGINE={engine!r} is not available; use one of {', '.join(ENGINES)}")
    missing = [key for key in ENGINES[engine] + REQUIRED if not env.get(key)]
    if missing:
        raise ConfigError(f"missing settings: {', '.join(missing)}")
    short = [key for key in ("WORKER_TOKEN", "IP_HMAC_KEY") if key in env and len(env[key]) < MIN_SECRET]
    if short:
        raise ConfigError(f"{', '.join(short)} must have at least {MIN_SECRET} characters")

    r = redis.Redis.from_url(env["REDIS_URL"], decode_responses=True)
    store = RedisStore(r)
    timeout = int(env.get("MODEL_TIMEOUT", "45"))
    canary = secrets.token_hex(12)  # new on every start: it shows up in a reply only if the prompt leaked
    system = system_prompt(facts, canary=canary)
    queue = WorkerQueue(r, system, timeout=timeout) if engine == "worker" else None
    model = queue or AnthropicModel(
        anthropic.Anthropic(api_key=env["ANTHROPIC_API_KEY"], timeout=timeout, max_retries=1),
        system,
        model=env.get("ANTHROPIC_MODEL", "claude-haiku-5-5"),
    )
    db = env["DATABASE_URL"]
    chat = ChatService(
        model,
        store,
        PostgresQuestionLog(db),
        new_session_id=lambda: secrets.token_urlsafe(32),
        guard=partial(check, canary=canary),
    )
    sink = SaveThenAlert(PostgresLeadSink(db), N8nAlert(env["LEAD_WEBHOOK_URL"]))
    lead = LeadService(sink, store, whatsapp=env["CONTACT_WHATSAPP"])
    return create_app(
        chat=chat,
        lead=lead,
        worker=queue,
        worker_token=env.get("WORKER_TOKEN", ""),
        ip_key=env["IP_HMAC_KEY"].encode(),
        origin=env.get("SITE_ORIGIN", "https://anthonymuniz.dev"),
    )


def app() -> FastAPI:
    api = build(os.environ, Path(os.environ.get("FACTS_PATH") or DEFAULT_FACTS).read_text(encoding="utf-8"))
    db = os.environ["DATABASE_URL"]
    try:
        ensure_schema(db)
    except psycopg.Error:
        log.warning("Postgres unreachable at startup: leads and the question log are down until it's back")
    threading.Thread(target=_purge_forever, args=(db,), daemon=True).start()
    return api


def _purge_forever(db: str) -> None:
    """Retention runs on a clock, not on traffic: delete expired leads and questions now and every 6 hours."""
    while True:
        try:
            purge_expired(db)
        except psycopg.Error:
            log.warning("retention purge failed; will try again")
        time.sleep(PURGE_EVERY)
