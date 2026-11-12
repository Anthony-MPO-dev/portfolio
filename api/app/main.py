"""Composition: wire the real adapters from the environment and build the API.

Responsibility: read the settings, refuse to start when a secret is missing or too short (there are no default
secrets), pick the model engine, plant a fresh canary in the system prompt on every start, and hand the use cases
their adapters, with the output guard bound to that canary and its hits (and the worker's) alerted to Anthony. Engines:
"anthropic" (Claude Haiku 5.5 through the API, on the author's personal account; the default when ANTHROPIC_API_KEY
is set, his decision of 2026-11-12; each answer's cost goes to the daily spend the use case caps) and "worker" (the
isolated chat worker on his PC, the default without a key).
Settings: REDIS_URL, DATABASE_URL, LEAD_WEBHOOK_URL, WORKER_TOKEN (32+ chars), IP_HMAC_KEY (32+ chars),
CONTACT_WHATSAPP; optional SITE_ORIGIN, MODEL_ENGINE, ANTHROPIC_API_KEY, ANTHROPIC_WORKSPACE_ID (only for a key that
isn't scoped to a workspace), TURNSTILE_SECRET (a new conversation then needs Cloudflare's browser proof),
MODEL_TIMEOUT (seconds), FACTS_PATH, SEARCH_MODEL_DIR (the fact search's model folder).
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

import hashlib
import logging
import os
import secrets
import threading
import time
from collections.abc import Mapping
from functools import partial
from pathlib import Path

import psycopg
import redis
from fastapi import FastAPI

from app.adapters.anthropic_model import AnthropicModel
from app.adapters.lead_alert import N8nAlert, SaveThenAlert
from app.adapters.onnx_embedder import E5_PREFIXES, OnnxEmbedder
from app.adapters.postgres import Db, PostgresLeadSink, PostgresQuestionLog, ensure_schema, purge_expired
from app.adapters.prompt import system_prompt
from app.adapters.redis_store import RedisAnswerCache, RedisStore
from app.adapters.security_alert import N8nSecurityAlert
from app.adapters.turnstile import TurnstileCheck
from app.adapters.worker_queue import WorkerQueue
from app.attachment_sandbox import convert_isolated
from app.http import create_app
from app.http_post import Poster
from app.output_guard import check
from app.search.passages import passages
from app.services.chat import ChatService
from app.services.lead import LeadService
from app.services.search import Embed, FactSearch, SearchService

log = logging.getLogger(__name__)
REQUIRED = ("REDIS_URL", "DATABASE_URL", "LEAD_WEBHOOK_URL", "WORKER_TOKEN", "IP_HMAC_KEY", "CONTACT_WHATSAPP")
MIN_SECRET = 32
PURGE_EVERY = 6 * 3600  # seconds
DEFAULT_FACTS = Path(__file__).resolve().parents[2] / "knowledge" / "facts.md"
DEFAULT_SEARCH_MODEL = "/app/models/multilingual-e5-small"  # downloaded into the image (api/Dockerfile)


class ConfigError(RuntimeError):
    """The API can't start with these settings."""


def build(env: Mapping[str, str], facts: str, embed: Embed | None = None) -> FastAPI:
    """`embed` turns texts into vectors for the fact search (the model app() loads); None leaves the search 503."""
    missing = [key for key in REQUIRED if not env.get(key)]
    if missing:
        raise ConfigError(f"missing settings: {', '.join(missing)}")
    short = [key for key in ("WORKER_TOKEN", "IP_HMAC_KEY") if len(env[key]) < MIN_SECRET]
    if short:
        raise ConfigError(f"{', '.join(short)} must have at least {MIN_SECRET} characters")
    engine = env.get("MODEL_ENGINE") or ("anthropic" if env.get("ANTHROPIC_API_KEY") else "worker")
    if engine not in ("worker", "anthropic"):
        raise ConfigError(f"MODEL_ENGINE={engine!r} is not available; use 'anthropic' or 'worker'")
    if engine == "anthropic" and not env.get("ANTHROPIC_API_KEY"):
        raise ConfigError("MODEL_ENGINE=anthropic needs ANTHROPIC_API_KEY")

    timeout = int(env.get("MODEL_TIMEOUT", "45"))
    # Two pooled clients: quick calls fail within seconds; the queue's blocking waits get their own, longer socket.
    r = redis.Redis.from_url(env["REDIS_URL"], decode_responses=True, socket_timeout=5, socket_connect_timeout=3)
    waits = redis.Redis.from_url(
        env["REDIS_URL"], decode_responses=True, socket_timeout=timeout + 15, socket_connect_timeout=3
    )
    store = RedisStore(r)
    post = Poster()  # one keep-alive pool and one circuit breaker for every webhook call
    alert = N8nSecurityAlert(env["LEAD_WEBHOOK_URL"], r, post=post)  # guard and worker hits, to Anthony's Telegram
    canary = secrets.token_hex(12)  # new on every start: it shows up in a reply only if the prompt leaked
    system = system_prompt(facts, canary=canary)
    queue = WorkerQueue(waits, system, timeout=timeout)
    model = queue
    if engine == "anthropic":
        model = AnthropicModel.connect(
            env["ANTHROPIC_API_KEY"], system, workspace=env.get("ANTHROPIC_WORKSPACE_ID"), timeout=timeout,
            on_cost=store.add_spend,
        )  # fmt: skip
    db = Db(env["DATABASE_URL"])  # pooled; opened by app(), so build stays free of network
    chat = ChatService(
        model,
        store,
        PostgresQuestionLog(db),
        new_session_id=lambda: secrets.token_urlsafe(32),
        guard=partial(check, canary=canary),
        alert=alert,
        # keyed by the prompt without the canary: new facts or rules start a fresh cache, a restart doesn't
        cache=RedisAnswerCache(r, version=hashlib.sha256(system_prompt(facts).encode()).hexdigest()[:12]),
        convert=convert_isolated,  # each upload in a locked-down child process, 3 at a time
        human=TurnstileCheck(env["TURNSTILE_SECRET"]) if env.get("TURNSTILE_SECRET") else None,
    )
    sink = SaveThenAlert(PostgresLeadSink(db), N8nAlert(env["LEAD_WEBHOOK_URL"], post=post))
    lead = LeadService(sink, store, whatsapp=env["CONTACT_WHATSAPP"])
    api = create_app(
        chat=chat,
        lead=lead,
        worker=queue,
        worker_token=env["WORKER_TOKEN"],
        ip_key=env["IP_HMAC_KEY"].encode(),
        origin=env.get("SITE_ORIGIN", "https://anthonymuniz.dev"),
        alert=alert,
        search=SearchService(FactSearch(passages(facts), embed), store) if embed else None,
    )
    api.state.db = db
    return api


def app() -> FastAPI:
    folder = Path(os.environ.get("SEARCH_MODEL_DIR") or DEFAULT_SEARCH_MODEL)
    embed = OnnxEmbedder(folder, E5_PREFIXES).embed if (folder / "model_quantized.onnx").exists() else None
    if embed is None:
        log.warning("no search model in %s: the fact search answers 503", folder)
    api = build(os.environ, Path(os.environ.get("FACTS_PATH") or DEFAULT_FACTS).read_text(encoding="utf-8"), embed)
    db = api.state.db
    db.open()
    try:
        ensure_schema(db)
    except psycopg.Error:
        log.warning("Postgres unreachable at startup: leads and the question log are down until it's back")
    threading.Thread(target=_purge_forever, args=(db,), daemon=True).start()
    return api


def _purge_forever(db: Db) -> None:
    """Retention runs on a clock, not on traffic: delete expired leads and questions now and every 6 hours."""
    while True:
        try:
            purge_expired(db)
        except psycopg.Error:
            log.warning("retention purge failed; will try again")
        time.sleep(PURGE_EVERY)
