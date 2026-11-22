"""Composition: wire the real adapters from the environment and build the API.

Responsibility: read the settings, refuse to start when a secret is missing or too short (there are no default
secrets), pick the model engine, plant a fresh canary in the system prompt on every start, and hand the use cases
their adapters (each one they call is traced, app.tracing; the alerts and the worker routes aren't), with the output
guard bound to that canary and its hits (and the worker's) alerted to Anthony. Engines:
"anthropic" (Claude Haiku 5.5 through the API, on the author's personal account; the default when ANTHROPIC_API_KEY
is set, his decision of 2026-11-12; each answer's cost goes to the daily spend the use case caps) and "worker" (the
isolated chat worker on his PC, the default without a key).
Settings: REDIS_URL, DATABASE_URL, LEAD_WEBHOOK_URL, WORKER_TOKEN (32+ chars), IP_HMAC_KEY (32+ chars),
CONTACT_WHATSAPP; optional SITE_ORIGIN, MODEL_ENGINE, ANTHROPIC_API_KEY, ANTHROPIC_WORKSPACE_ID (only for a key that
isn't scoped to a workspace), TURNSTILE_SECRET (a new conversation then needs Cloudflare's browser proof),
MODEL_TIMEOUT (seconds), FACTS_PATH, SEARCH_MODEL_DIR (the fact search's model folder), TRACE_SLOW_MS (a request
this slow or slower logs its trace; default 2000).
Public API: build (pure: no network, no disk), app (the uvicorn factory: reads the facts and starts the thread that
creates the tables and purges expired rows, every 6 hours or a minute after Postgres failed), ConfigError.
Run: uvicorn app.main:app --factory
Used by: the Docker image.
Depends on: every adapter, app.http, app.tracing, the use cases.
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
from app.tracing import TraceRequests, make_tracer, traced

log = logging.getLogger(__name__)
REQUIRED = ("REDIS_URL", "DATABASE_URL", "LEAD_WEBHOOK_URL", "WORKER_TOKEN", "IP_HMAC_KEY", "CONTACT_WHATSAPP")
MIN_SECRET = 32
PURGE_EVERY = 6 * 3600  # seconds
RETRY = 60  # seconds, after Postgres failed
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
    tracer = make_tracer(int(env.get("TRACE_SLOW_MS", "2000")))
    # Two pooled clients: quick calls fail within seconds; the queue's blocking waits get their own, longer socket.
    r = redis.Redis.from_url(env["REDIS_URL"], decode_responses=True, socket_timeout=5, socket_connect_timeout=3)
    waits = redis.Redis.from_url(
        env["REDIS_URL"], decode_responses=True, socket_timeout=timeout + 15, socket_connect_timeout=3
    )
    store = traced(RedisStore(r), "redis", tracer)
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
    model = traced(model, "model", tracer)
    db = Db(env["DATABASE_URL"])  # pooled; opened by app(), so build stays free of network
    chat = ChatService(
        model,
        store,
        traced(PostgresQuestionLog(db), "postgres", tracer),
        new_session_id=lambda: secrets.token_urlsafe(32),
        guard=partial(check, canary=canary),
        alert=alert,
        # keyed by the prompt without the canary: new facts or rules start a fresh cache, a restart doesn't
        cache=traced(
            RedisAnswerCache(r, version=hashlib.sha256(system_prompt(facts).encode()).hexdigest()[:12]), "cache", tracer
        ),
        convert=traced(convert_isolated, "attachment", tracer),  # each upload in a locked-down child process, 3 at a time
        human=traced(TurnstileCheck(env["TURNSTILE_SECRET"]), "turnstile", tracer) if env.get("TURNSTILE_SECRET") else None,
    )
    sink = traced(SaveThenAlert(PostgresLeadSink(db), N8nAlert(env["LEAD_WEBHOOK_URL"], post=post)), "lead", tracer)
    lead = LeadService(sink, store, whatsapp=env["CONTACT_WHATSAPP"])
    api = create_app(
        chat=chat,
        lead=lead,
        worker=queue if engine == "worker" else None,  # the PC's job routes only when the PC is the engine
        worker_token=env["WORKER_TOKEN"],
        ip_key=env["IP_HMAC_KEY"].encode(),
        origin=env.get("SITE_ORIGIN", "https://anthonymuniz.dev"),
        alert=alert,
        search=SearchService(FactSearch(passages(facts), traced(embed, "embed", tracer)), store) if embed else None,
    )
    api.add_middleware(TraceRequests, tracer=tracer)
    api.state.db = db
    return api


def app() -> FastAPI:
    folder = Path(os.environ.get("SEARCH_MODEL_DIR") or DEFAULT_SEARCH_MODEL)
    embed = OnnxEmbedder(folder, E5_PREFIXES).embed if (folder / "model_quantized.onnx").exists() else None
    if embed is None:
        log.warning("no search model in %s: the fact search answers 503", folder)
    api = build(os.environ, Path(os.environ.get("FACTS_PATH") or DEFAULT_FACTS).read_text(encoding="utf-8"), embed)
    api.state.db.open()
    threading.Thread(target=_purge_forever, args=(api.state.db,), daemon=True).start()
    return api


def _purge_forever(db: Db) -> None:
    """Retention runs on a clock, not on traffic: create the tables if they're missing (Postgres may have been down
    at startup), then delete expired leads and questions; again in 6 hours, or in a minute when Postgres failed."""
    while True:
        try:
            ensure_schema(db)
            purge_expired(db)
            wait = PURGE_EVERY
        except psycopg.Error:
            log.warning("Postgres unreachable: leads and the question log are down; trying again in a minute")
            wait = RETRY
        time.sleep(wait)
