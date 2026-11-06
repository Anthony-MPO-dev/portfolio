"""HTTP layer of the chat API.

Responsibility: translate HTTP into the use cases and back, nothing else. Browser routes (/api/chat, /api/lead) take
JSON only and refuse other sites (Sec-Fetch-Site, then Origin). The session lives in the __Host-chat_sid cookie
(Secure, HttpOnly, SameSite=Strict, no Max-Age), set only when the server created a new session. The visitor's IP
becomes an HMAC before it reaches any use case. Worker routes need the bearer token. Every answer is no-store and
there are no public API docs.
Public API: create_app.
Used by: app.main (composition with the real adapters) and tests/test_http.py (with fakes).
Depends on: FastAPI, app.services.chat.ChatService, app.services.lead.LeadService, a worker queue
(next_job, finish), the standard library hmac.
Tests: tests/test_http.py.
"""

import hashlib
import hmac
from typing import Protocol

from fastapi import Depends, FastAPI, HTTPException, Path, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.services.chat import ChatService
from app.services.lead import LeadService

COOKIE = "__Host-chat_sid"
COOKIE_FLAGS = {"path": "/", "secure": True, "httponly": True, "samesite": "strict"}
CODES = {
    "ok": 200,
    "offline": 200,
    "invalid": 400,
    "rate_limited": 429,
    "busy": 429,
    "conversation_limit": 429,
    "unavailable": 503,
}


class Worker(Protocol):
    def next_job(self, wait: int) -> dict | None: ...
    def finish(self, job_id: str, raw: str) -> None: ...


class ChatIn(BaseModel):
    message: str = Field(max_length=2000)  # the use case enforces the real 500-character limit
    page_lang: str = Field("en", max_length=10)


class LeadIn(BaseModel):
    name: str = Field("", max_length=300)
    company: str = Field("", max_length=300)
    email: str = Field("", max_length=300)
    linkedin: str = Field("", max_length=300)
    kind: str = Field("", max_length=20)
    page_lang: str = Field("en", max_length=10)
    website: str = Field("", max_length=300)  # honeypot: hidden from people, filled by bots


class AnswerIn(BaseModel):
    answer: str = Field(max_length=20_000)


def create_app(
    *, chat: ChatService, lead: LeadService, worker: Worker, worker_token: str, ip_key: bytes, origin: str
) -> FastAPI:
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
        content_type = request.headers.get("content-type", "").split(";")[0].strip()
        if request.method == "POST" and content_type != "application/json":
            raise HTTPException(415)

    def worker_auth(request: Request) -> None:
        sent = request.headers.get("authorization", "").encode()
        if not worker_token or not hmac.compare_digest(sent, f"Bearer {worker_token}".encode()):
            raise HTTPException(401)

    def client_key(request: Request) -> str:
        ip = request.client.host if request.client else ""
        return hmac.new(ip_key, ip.encode(), hashlib.sha256).hexdigest()[:32]

    browser = [Depends(same_origin)]

    @app.post("/api/chat", dependencies=browser)
    def post_chat(body: ChatIn, request: Request) -> Response:
        sid = request.cookies.get(COOKIE)
        result = chat.answer(
            session_id=sid, client_key=client_key(request), message=body.message, page_lang=body.page_lang
        )
        response = JSONResponse(
            {"status": result.status, "reply": result.reply, "offer_contact": result.offer_contact},
            CODES[result.status],
        )
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

    @app.get("/api/worker/next", dependencies=[Depends(worker_auth)])
    def next_job(wait: int = Query(20, ge=1, le=25)) -> Response:
        job = worker.next_job(wait)
        return JSONResponse(job) if job else Response(status_code=204)

    @app.post("/api/worker/jobs/{job_id}", status_code=204, dependencies=[Depends(worker_auth)])
    def finish_job(body: AnswerIn, job_id: str = Path(pattern="^[0-9a-f]{32}$")) -> Response:
        worker.finish(job_id, body.answer)
        return Response(status_code=204)

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    return app
