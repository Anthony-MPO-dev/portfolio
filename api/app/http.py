"""HTTP layer of the chat API.

Responsibility: translate HTTP into the use cases and back, nothing else. Browser routes (/api/chat, /api/lead) take
JSON only, /api/attachments one file as raw bytes (10 MB at most), and all refuse other sites (Sec-Fetch-Site,
then Origin). The session lives in the __Host-chat_sid cookie
(Secure, HttpOnly, SameSite=Strict, no Max-Age), set only when the server created a new session. The visitor's IP
(through Cloudflare, see app.client_ip) becomes an HMAC before it reaches any use case. Worker routes need the bearer token. Every answer is no-store and
there are no public API docs.
Public API: create_app.
Used by: app.main (composition with the real adapters) and tests/test_http.py (with fakes).
Depends on: FastAPI, app.services.chat.ChatService, app.services.lead.LeadService, app.ports.WorkerJobs,
app.client_ip, the standard library hmac.
Tests: tests/test_http.py.
"""

import hashlib
import json
from collections.abc import Callable
from typing import Annotated
import hmac

from fastapi import Depends, FastAPI, HTTPException, Path, Query, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.client_ip import client_ip, ip_source
from app.ports import WorkerJobs
from app.services.chat import ChatService
from app.services.lead import LeadService

COOKIE = "__Host-chat_sid"
COOKIE_FLAGS = {"path": "/", "secure": True, "httponly": True, "samesite": "strict"}
CODES = {
    "ok": 200,
    "offline": 200,
    "blocked": 200,
    "invalid": 400,
    "rate_limited": 429,
    "busy": 429,
    "conversation_limit": 429,
    "unavailable": 503,
    "rejected": 422,
    "too_many": 429,
}
MAX_UPLOAD = 10 * 1024 * 1024  # the largest file app.attachments takes; each type has its own, smaller limit too
FileId = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,40}$")]


class ChatIn(BaseModel):
    message: str = Field(max_length=2000)  # the use case enforces the real 500-character limit
    page_lang: str = Field("en", max_length=10)
    attachments: list[FileId] = Field(default_factory=list, max_length=3)  # ids from /api/attachments


class LeadIn(BaseModel):
    name: str = Field("", max_length=300)
    company: str = Field("", max_length=300)
    email: str = Field("", max_length=300)
    linkedin: str = Field("", max_length=300)
    kind: str = Field("", max_length=20)
    page_lang: str = Field("en", max_length=10)
    website: str = Field("", max_length=300)  # honeypot: hidden from people, filled by bots


class ChunkIn(BaseModel):
    text: str = Field(max_length=5_000)


class AnswerIn(BaseModel):
    answer: str = Field(max_length=20_000)
    alert: str | None = Field(None, pattern=r"^[A-Za-z0-9 _:,./-]{1,80}$")  # a short label from the worker's checks


def create_app(
    *,
    chat: ChatService,
    lead: LeadService,
    worker: WorkerJobs | None,
    worker_token: str,
    ip_key: bytes,
    origin: str,
    alert: Callable[[str], None] = lambda reason: None,
) -> FastAPI:
    """`worker` is the local-worker engine's job queue; None (another engine) leaves the worker routes out."""
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def no_store(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    def same_origin(request: Request) -> None:
        site, sent_origin = request.headers.get("sec-fetch-site"), request.headers.get("origin")
        if (site and site != "same-origin") or (sent_origin and sent_origin != origin):
            raise HTTPException(403)

    def body_type(expected: str):
        """Neither JSON nor raw bytes can be posted by another site's form without a CORS preflight, and there is
        no CORS here."""

        def check(request: Request) -> None:
            content_type = request.headers.get("content-type", "").split(";")[0].strip()
            if request.method == "POST" and content_type != expected:
                raise HTTPException(415)

        return Depends(check)

    def worker_auth(request: Request) -> None:
        sent = request.headers.get("authorization", "").encode()
        if not worker_token or not hmac.compare_digest(sent, f"Bearer {worker_token}".encode()):
            raise HTTPException(401)

    def client_key(request: Request) -> str:
        ip = client_ip(request.client.host if request.client else "", request.headers)
        return hmac.new(ip_key, ip.encode(), hashlib.sha256).hexdigest()[:32]

    browser = [Depends(same_origin), body_type("application/json")]
    upload = [Depends(same_origin), body_type("application/octet-stream")]

    @app.post("/api/chat", dependencies=browser)
    def post_chat(body: ChatIn, request: Request) -> Response:
        sid = request.cookies.get(COOKIE)
        result = chat.answer(
            session_id=sid,
            client_key=client_key(request),
            message=body.message,
            page_lang=body.page_lang,
            attachments=body.attachments,
        )
        if result.events is not None:  # the answer streams: one JSON event per line, as it is written
            lines = (json.dumps(event, ensure_ascii=False) + "\n" for event in result.events)
            response = StreamingResponse(lines, media_type="application/x-ndjson", headers={"X-Accel-Buffering": "no"})
        else:
            response = JSONResponse(
                {"status": result.status, "reply": result.reply, "offer_contact": result.offer_contact},
                CODES[result.status],
            )
        if result.session_id and result.session_id != sid:
            response.set_cookie(COOKIE, result.session_id, **COOKIE_FLAGS)
        return response

    @app.post("/api/attachments", dependencies=upload)
    async def post_attachment(request: Request) -> Response:
        """One file as the raw request body, read in memory and never past 10 MB."""
        declared, data = int(request.headers.get("content-length") or 0), bytearray()
        if declared <= MAX_UPLOAD:
            async for piece in request.stream():
                data += piece
                if len(data) > MAX_UPLOAD:
                    break
        too_big = declared > MAX_UPLOAD or len(data) > MAX_UPLOAD
        if too_big or not data:
            reason, code = ("too_big", 413) if too_big else ("unreadable", 422)
            return JSONResponse({"status": "rejected", "reason": reason}, code)
        sid = request.cookies.get(COOKIE)
        result = await run_in_threadpool(chat.attach, session_id=sid, client_key=client_key(request), data=bytes(data))
        body = {"status": result.status} | ({"id": result.id, "summary": result.summary} if result.status == "ok" else {})
        response = JSONResponse(body | ({"reason": result.reason} if result.reason else {}), CODES[result.status])
        if result.session_id and result.session_id != sid:
            response.set_cookie(COOKIE, result.session_id, **COOKIE_FLAGS)
        return response

    @app.delete("/api/chat", status_code=204, dependencies=browser)
    def delete_chat(request: Request) -> Response:
        chat.forget(request.cookies.get(COOKIE))
        response = Response(status_code=204)
        response.delete_cookie(COOKIE, **COOKIE_FLAGS)
        return response

    @app.post("/api/lead", dependencies=browser)
    def post_lead(body: LeadIn, request: Request) -> Response:
        result = lead.submit(
            name=body.name,
            company=body.company,
            email=body.email,
            linkedin=body.linkedin,
            kind=body.kind,
            page_lang=body.page_lang,
            client_key=client_key(request),
            honeypot=body.website,
        )
        payload = {"status": result.status} | ({"whatsapp": result.whatsapp} if result.whatsapp else {})
        return JSONResponse(payload, CODES[result.status])

    if worker is not None:

        @app.get("/api/worker/next", dependencies=[Depends(worker_auth)])
        def next_job(wait: int = Query(20, ge=1, le=25)) -> Response:
            job = worker.next_job(wait)
            return JSONResponse(job) if job else Response(status_code=204)

        @app.post("/api/worker/jobs/{job_id}/chunks", status_code=204, dependencies=[Depends(worker_auth)])
        def stream_job(body: ChunkIn, job_id: str = Path(pattern="^[0-9a-f]{32}$")) -> Response:
            worker.chunk(job_id, body.text)
            return Response(status_code=204)

        @app.post("/api/worker/jobs/{job_id}", status_code=204, dependencies=[Depends(worker_auth)])
        def finish_job(body: AnswerIn, job_id: str = Path(pattern="^[0-9a-f]{32}$")) -> Response:
            worker.finish(job_id, body.answer)
            if body.alert:
                alert(f"worker: {body.alert}")
            return Response(status_code=204)

    @app.get("/api/health")
    def health(request: Request) -> dict:
        # How the caller's address was read (never the address): "shared" means the proxy chain hides visitors.
        return {"ok": True, "ip": ip_source(request.client.host if request.client else "", request.headers)}

    return app
