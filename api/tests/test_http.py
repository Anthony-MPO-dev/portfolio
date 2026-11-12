"""HTTP layer: routes translate requests into the use cases, set the session cookie and guard the worker routes."""

import json
import pytest
from fastapi.testclient import TestClient

from app.http import create_app
from app.services.search import FactSearch, SearchService
from tests.test_search import PASSAGES, fake_embed
from app.ports import Attachment, AttachmentRejected, ModelReply
from app.services.chat import ChatService, Limits
from app.services.lead import LeadService
from tests.fakes import FakeFormCounter, FakeLeadSink, FakeModel, FakeQuestionLog, FakeStore

ORIGIN = "https://anthonymuniz.dev"
TOKEN = "worker-secret"
SAME_SITE = {"Sec-Fetch-Site": "same-origin"}
RAW = {**SAME_SITE, "Content-Type": "application/octet-stream"}
PDF = Attachment("pdf", "pdf, 3 pages", text="Invoice 42")
LEAD = {"name": "Jane", "company": "Acme", "email": "jane@acme.com", "kind": "hiring", "page_lang": "en"}


class FakeWorker:
    def __init__(self, jobs=()):
        self.jobs = list(jobs)
        self.finished, self.chunks = [], []

    def next_job(self, wait):
        return self.jobs.pop(0) if self.jobs else None

    def chunk(self, job_id, text):
        self.chunks.append((job_id, text))

    def finish(self, job_id, raw):
        self.finished.append((job_id, raw))


def events(response):
    """The NDJSON lines of a streamed answer."""
    assert response.headers["content-type"].startswith("application/x-ndjson")
    return [json.loads(line) for line in response.text.splitlines() if line]


class World:
    def __init__(self, model=None, limits=Limits(), jobs=(), peer="testclient", engine="worker", guard=None, convert=None,
                 human=None, search=True):  # fmt: skip
        self.alerts = []
        self.model = model or FakeModel()
        self.store = FakeStore()
        self.sink = FakeLeadSink()
        self.worker = FakeWorker(jobs)
        ids = (f"sid-{n}" for n in range(1, 1000))
        self.converted = []
        convert = convert or (lambda data: self.converted.append(data) or PDF)
        chat = ChatService(self.model, self.store, FakeQuestionLog(), lambda: next(ids), limits, guard or (lambda r: None),
                           convert=convert, human=human)  # fmt: skip
        lead = LeadService(self.sink, FakeFormCounter(), whatsapp="+00 0000")
        worker = self.worker if engine == "worker" else None
        app = create_app(
            chat=chat, lead=lead, worker=worker, worker_token=TOKEN, ip_key=b"k", origin=ORIGIN, alert=self.alerts.append,
            search=SearchService(FactSearch(PASSAGES, fake_embed), self.store) if search else None
        )
        self.client = TestClient(app, base_url=ORIGIN, client=(peer, 50000))

    def chat(self, message="hi", headers=SAME_SITE, **body):
        return self.client.post("/api/chat", json={"message": message, "page_lang": "en", **body}, headers=headers)


def test_new_visitor_gets_the_reply_and_a_strict_session_cookie():
    world = World(FakeModel(ModelReply("Hi there.", offer_contact=True)))
    response = world.chat()
    cookie = response.headers["set-cookie"].lower()
    assert events(response) == [
        {"type": "delta", "text": "Hi "},
        {"type": "delta", "text": "there."},
        {"type": "done", "status": "ok", "offer_contact": True},
    ]
    assert response.headers["x-accel-buffering"] == "no" and "no-store" in response.headers["cache-control"]
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
    assert (response.status_code, events(response)) == (200, [{"type": "done", "status": "offline", "offer_contact": True}])


def test_a_blocked_reply_is_a_normal_answer_without_the_text():
    response = World(FakeModel(ModelReply("leak", offer_contact=False)), guard=lambda reply: "secret").chat()
    assert (response.status_code, events(response)) == (200, [{"type": "done", "status": "blocked", "offer_contact": True}])


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


def test_health_check_says_how_the_callers_address_was_read_never_the_address():
    assert World().client.get("/api/health").json() == {"ok": True, "ip": "unknown"}


def test_a_worker_alert_reaches_anthony_and_the_job_still_ends():
    world = World()
    auth = {"Authorization": f"Bearer {TOKEN}"}
    done = world.client.post(f"/api/worker/jobs/{'b' * 32}", json={"answer": "", "alert": "tool_use: Read"}, headers=auth)
    assert (done.status_code, world.worker.finished, world.alerts) == (204, [("b" * 32, "")], ["worker: tool_use: Read"])


def test_a_worker_alert_with_markup_or_too_long_is_refused():
    world = World()
    auth = {"Authorization": f"Bearer {TOKEN}"}
    for alert in ("<b>hi</b>", "x" * 200):
        response = world.client.post(f"/api/worker/jobs/{'b' * 32}", json={"answer": "", "alert": alert}, headers=auth)
        assert response.status_code == 422
    assert world.alerts == []


def test_the_worker_streams_pieces_of_the_answer():
    world = World()
    auth = {"Authorization": f"Bearer {TOKEN}"}
    done = world.client.post(f"/api/worker/jobs/{'c' * 32}/chunks", json={"text": "He has "}, headers=auth)
    refused = world.client.post(f"/api/worker/jobs/{'c' * 32}/chunks", json={"text": "x"})
    assert (done.status_code, refused.status_code, world.worker.chunks) == (204, 401, [("c" * 32, "He has ")])


def test_a_file_goes_up_as_raw_bytes_and_comes_back_as_an_id_and_a_summary():
    world = World()
    response = world.client.post("/api/attachments", content=b"%PDF-1.7", headers=RAW)
    assert (response.status_code, response.json()) == (200, {"status": "ok", "id": "file-1", "summary": "pdf, 3 pages"})
    assert response.headers["set-cookie"].lower().startswith("__host-chat_sid=sid-1;")
    assert world.converted == [b"%PDF-1.7"]


@pytest.mark.parametrize("headers", [{**SAME_SITE, "Content-Type": "multipart/form-data; boundary=x"},
                                     {"Sec-Fetch-Site": "cross-site", "Content-Type": "application/octet-stream"}])  # fmt: skip
def test_an_upload_must_be_raw_bytes_from_this_site(headers):
    world = World()
    status = world.client.post("/api/attachments", content=b"%PDF", headers=headers).status_code
    assert (status, world.converted) in [(415, []), (403, [])]


def test_an_upload_over_10_mb_is_refused_before_any_conversion():
    world = World()
    response = world.client.post("/api/attachments", content=b"x" * (10 * 1024 * 1024 + 1), headers=RAW)
    assert (response.status_code, response.json(), world.converted) == (413, {"status": "rejected", "reason": "too_big"}, [])


def test_a_refused_file_says_why():
    def refuse(data):
        raise AttachmentRejected("type")

    response = World(convert=refuse).client.post("/api/attachments", content=b"MZ", headers=RAW)
    assert (response.status_code, response.json()) == (422, {"status": "rejected", "reason": "type"})


def test_the_message_names_its_files_and_the_model_gets_them():
    world = World()
    file_id = world.client.post("/api/attachments", content=b"%PDF", headers=RAW).json()["id"]
    events(world.chat("What is this?", attachments=[file_id]))
    assert world.model.calls[-1].attachments == [PDF]


@pytest.mark.parametrize("ids", [["../x:*"], ["a"] * 4])
def test_file_ids_must_be_short_plain_tokens_and_3_at_most(ids):
    world = World()
    assert (world.chat(attachments=ids).status_code, world.model.calls) == (422, [])


def test_the_browser_proof_rides_in_the_chat_body_and_in_a_header_for_uploads():
    seen = []
    world = World(human=lambda token: seen.append(token) or token == "real-browser")
    refused = world.chat(human="script")
    assert (refused.status_code, refused.json()["status"]) == (200, "challenge")
    upload = world.client.post("/api/attachments", content=b"%PDF", headers={**RAW, "X-Human": "real-browser"})
    assert upload.json()["status"] == "ok"
    assert seen == ["script", "real-browser"]


def test_the_map_of_facts_is_public_and_cached_for_an_hour():
    response = World().client.get("/api/search/facts")
    facts = response.json()["facts"]
    assert len(facts) == len(PASSAGES) and set(facts[0]) == {"id", "section", "text", "x", "y"}
    assert "max-age=3600" in response.headers["cache-control"]


def test_a_search_answers_with_the_hits_and_the_question_s_place():
    response = World().client.post("/api/search", json={"q": "Does Kai use ChromaDB?"}, headers=SAME_SITE)
    data = response.json()
    assert response.status_code == 200 and data["hits"][0]["id"] == 3 and {"x", "y"} <= set(data)
    assert "no-store" in response.headers["cache-control"]


def test_a_search_from_another_site_or_too_long_is_refused():
    world = World()
    assert world.client.post("/api/search", json={"q": "x"}, headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert world.client.post("/api/search", json={"q": "x" * 201}, headers=SAME_SITE).status_code == 400


def test_without_the_model_the_search_says_it_is_unavailable():
    world = World(search=False)
    assert world.client.get("/api/search/facts").status_code == 503
    assert world.client.post("/api/search", json={"q": "x"}, headers=SAME_SITE).status_code == 503
