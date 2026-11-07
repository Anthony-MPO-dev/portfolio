"""HTTP layer: routes translate requests into the use cases, set the session cookie and guard the worker routes."""

import pytest
from fastapi.testclient import TestClient

from app.http import create_app
from app.ports import ModelReply
from app.services.chat import ChatService, Limits
from app.services.lead import LeadService
from tests.fakes import FakeFormCounter, FakeLeadSink, FakeModel, FakeQuestionLog, FakeStore

ORIGIN = "https://anthonymuniz.dev"
TOKEN = "worker-secret"
SAME_SITE = {"Sec-Fetch-Site": "same-origin"}
LEAD = {"name": "Jane", "company": "Acme", "email": "jane@acme.com", "kind": "hiring", "page_lang": "en"}


class FakeWorker:
    def __init__(self, jobs=()):
        self.jobs = list(jobs)
        self.finished = []

    def next_job(self, wait):
        return self.jobs.pop(0) if self.jobs else None

    def finish(self, job_id, raw):
        self.finished.append((job_id, raw))


class World:
    def __init__(self, model=None, limits=Limits(), jobs=(), peer="testclient", engine="worker"):
        self.model = model or FakeModel()
        self.store = FakeStore()
        self.sink = FakeLeadSink()
        self.worker = FakeWorker(jobs)
        ids = (f"sid-{n}" for n in range(1, 1000))
        chat = ChatService(self.model, self.store, FakeQuestionLog(), lambda: next(ids), limits)
        lead = LeadService(self.sink, FakeFormCounter(), whatsapp="+00 0000")
        worker = self.worker if engine == "worker" else None
        app = create_app(chat=chat, lead=lead, worker=worker, worker_token=TOKEN, ip_key=b"k", origin=ORIGIN)
        self.client = TestClient(app, base_url=ORIGIN, client=(peer, 50000))

    def chat(self, message="hi", headers=SAME_SITE, **body):
        return self.client.post("/api/chat", json={"message": message, "page_lang": "en", **body}, headers=headers)


def test_new_visitor_gets_the_reply_and_a_strict_session_cookie():
    world = World(FakeModel(ModelReply("Hi there.", offer_contact=True)))
    response = world.chat()
    cookie = response.headers["set-cookie"].lower()
    assert response.json() == {"status": "ok", "reply": "Hi there.", "offer_contact": True}
    assert cookie.startswith("__host-chat_sid=sid-1;")
    assert all(flag in cookie for flag in ("secure", "httponly", "samesite=strict", "path=/"))
    assert "max-age" not in cookie and "expires" not in cookie


def test_the_cookie_carries_the_conversation_and_is_not_set_again():
    world = World()
    world.chat("Who is he?")
    second = world.chat("And his stack?")
    assert ("set-cookie" not in second.headers, len(world.model.calls[-1].history)) == (True, 2)


def test_message_that_is_not_json_is_refused_before_the_model():
    world = World()
    response = world.client.post("/api/chat", content="message=hi", headers={**SAME_SITE, "Content-Type": "text/plain"})
    assert (response.status_code, world.model.calls) == (415, [])


@pytest.mark.parametrize(
    "headers", [{"Sec-Fetch-Site": "cross-site"}, {"Sec-Fetch-Site": "same-site"}, {"Origin": "https://evil.example"}]
)
def test_requests_from_other_sites_are_refused(headers):
    world = World()
    assert (world.chat(headers=headers).status_code, world.model.calls) == (403, [])


def test_limits_come_back_as_429_with_the_status():
    world = World(limits=Limits(per_ip_hour=1))
    world.chat()
    response = world.chat()
    assert (response.status_code, response.json()["status"]) == (429, "rate_limited")


def test_offline_is_a_normal_answer_with_the_contact_offer():
    response = World(FakeModel(unavailable=True)).chat()
    assert (response.status_code, response.json()) == (200, {"status": "offline", "reply": None, "offer_contact": True})


def test_the_visitor_ip_is_never_stored_as_is():
    world = World()
    world.chat()
    assert [key for key in world.store.ip_day if "testclient" in key] == [] and len(world.store.ip_day) == 1


def test_visitors_behind_the_same_cloudflare_edge_do_not_share_a_limit():
    world = World(limits=Limits(per_ip_hour=1), peer="162.158.10.1")
    first = world.chat(headers={**SAME_SITE, "CF-Connecting-IP": "203.0.113.7"})
    world.client.cookies.clear()
    second = world.chat(headers={**SAME_SITE, "CF-Connecting-IP": "203.0.113.8"})
    assert (first.status_code, second.status_code) == (200, 200)


def test_erase_conversation_removes_it_and_clears_the_cookie():
    world = World()
    world.chat("My name is Jane")
    response = world.client.delete("/api/chat", headers=SAME_SITE)
    world.client.cookies.clear()
    assert (response.status_code, world.store.histories, "__Host-chat_sid=\"\"" in response.headers["set-cookie"]) == (
        204,
        {},
        True,
    )


def test_hiring_lead_gets_the_whatsapp_number_and_project_lead_does_not():
    world = World()
    hiring = world.client.post("/api/lead", json=LEAD, headers=SAME_SITE).json()
    project = world.client.post("/api/lead", json={**LEAD, "kind": "project"}, headers=SAME_SITE).json()
    assert (hiring, project, len(world.sink.saved)) == (
        {"status": "ok", "whatsapp": "+00 0000"},
        {"status": "ok"},
        2,
    )


def test_invalid_lead_is_a_400():
    response = World().client.post("/api/lead", json={**LEAD, "email": "nope"}, headers=SAME_SITE)
    assert (response.status_code, response.json()) == (400, {"status": "invalid"})


def test_lead_with_the_hidden_field_filled_looks_saved_but_is_dropped():
    world = World()
    response = world.client.post("/api/lead", json={**LEAD, "website": "spam.example"}, headers=SAME_SITE)
    assert (response.json(), world.sink.saved) == ({"status": "ok"}, [])


@pytest.mark.parametrize("auth", [None, "Bearer wrong", "worker-secret"])
def test_worker_routes_need_the_token(auth):
    world = World(jobs=[{"id": "a" * 32}])
    headers = {"Authorization": auth} if auth else {}
    responses = [
        world.client.get("/api/worker/next", headers=headers),
        world.client.post(f"/api/worker/jobs/{'a' * 32}", json={"answer": "x"}, headers=headers),
    ]
    assert [r.status_code for r in responses] == [401, 401] and world.worker.finished == []


def test_worker_takes_a_job_and_hands_the_answer_back():
    job = {"id": "a" * 32, "system": "s", "prompt": "p"}
    world = World(jobs=[job])
    auth = {"Authorization": f"Bearer {TOKEN}"}
    taken = world.client.get("/api/worker/next?wait=1", headers=auth)
    idle = world.client.get("/api/worker/next?wait=1", headers=auth)
    done = world.client.post(f"/api/worker/jobs/{'a' * 32}", json={"answer": "raw"}, headers=auth)
    assert (taken.json(), idle.status_code, done.status_code, world.worker.finished) == (
        job,
        204,
        204,
        [("a" * 32, "raw")],
    )


def test_another_engine_leaves_the_worker_routes_out():
    world = World(engine="anthropic")
    auth = {"Authorization": f"Bearer {TOKEN}"}
    assert world.client.get("/api/worker/next", headers=auth).status_code == 404


def test_api_answers_are_never_cached_and_there_are_no_public_docs():
    world = World()
    assert world.chat().headers["cache-control"] == "no-store"
    assert [world.client.get(p).status_code for p in ("/docs", "/openapi.json")] == [404, 404]


def test_health_check():
    assert World().client.get("/api/health").json() == {"ok": True}
