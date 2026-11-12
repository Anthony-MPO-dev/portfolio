"""Chat use case with files: upload, limits and switch, the files reaching the model, and what the history keeps."""

from app.ports import Attachment, AttachmentRejected, ModelReply
from app.services.chat import ChatService, Limits
from tests.fakes import FakeCache, FakeModel, FakeQuestionLog, FakeStore

IP = "client-a"
PDF = Attachment("pdf", "pdf, 3 pages", text="Invoice 42")
IMAGE = Attachment("image", "image, 30x20", png=b"png-bytes")
FILES = {b"%PDF": PDF, b"\x89PNG": IMAGE}


def convert(data: bytes) -> Attachment:
    if data not in FILES:
        raise AttachmentRejected("type")
    return FILES[data]


def make(model=None, limits=Limits(), cache=None):
    model, store = model or FakeModel(), FakeStore()
    ids = (f"sid-{n}" for n in range(1, 1000))
    chat = ChatService(model=model, store=store, log=FakeQuestionLog(), new_session_id=lambda: next(ids),
                       limits=limits, convert=convert, **({"cache": cache} if cache is not None else {}))  # fmt: skip
    return chat, model, store


def upload(chat, data=b"%PDF", sid=None, ip=IP):
    return chat.attach(session_id=sid, client_key=ip, data=data)


def ask(chat, message, sid, files=(), ip=IP):
    result = chat.answer(session_id=sid, client_key=ip, message=message, page_lang="en", attachments=list(files))
    if result.events is not None:
        events = list(result.events)
        return events[-1]["status"]
    return result.status


def test_an_uploaded_file_is_converted_and_kept_for_its_session():
    chat, _, store = make()
    up = upload(chat)
    assert (up.status, up.session_id, up.summary) == ("ok", "sid-1", "pdf, 3 pages")
    assert store.attachments("sid-1", [up.id]) == [PDF]


def test_a_refused_file_says_why_and_is_not_kept():
    chat, _, store = make()
    up = upload(chat, b"MZ")
    assert (up.status, up.reason, store.files) == ("rejected", "type", {})


def test_a_conversation_takes_10_files_at_most():
    chat, _, _ = make(limits=Limits(per_ip_hour=100, per_ip_day=100, upload_ip_hour=100, upload_ip_day=100))
    sid = upload(chat).session_id
    statuses = [upload(chat, sid=sid).status for _ in range(10)]
    assert statuses == ["ok"] * 9 + ["too_many"]


def test_uploads_have_their_own_ip_limit_and_leave_the_message_limit_alone():
    chat, _, _ = make(limits=Limits(per_ip_hour=1, upload_ip_hour=2))
    statuses = [upload(chat).status for _ in range(3)]
    assert (statuses, ask(chat, "Hi", None)) == (["ok", "ok", "rate_limited"], "ok")


def test_switching_files_off_also_stops_the_files_already_uploaded():
    chat, model, store = make()
    pdf = upload(chat)
    store.files_off = True
    assert (ask(chat, "Read this", pdf.session_id, [pdf.id]), model.calls, store.files) == ("offline", [], {})
    assert ask(chat, "And in text?", pdf.session_id) == "ok"


def test_uploads_are_refused_while_the_chat_or_the_attachments_are_switched_off():
    chat, _, store = make()
    store.files_off = True
    assert upload(chat).status == "offline"
    store.files_off, store.off = False, True
    assert upload(chat).status == "offline"


def test_the_files_reach_the_model_and_the_history_keeps_one_line_each():
    chat, model, store = make(FakeModel(ModelReply("It is invoice 42.", offer_contact=False)))
    pdf = upload(chat)
    image = upload(chat, b"\x89PNG", sid=pdf.session_id)
    assert ask(chat, "What is in these?", pdf.session_id, [pdf.id, image.id]) == "ok"
    assert model.calls[-1].attachments == [PDF, IMAGE]
    assert store.histories[pdf.session_id][0]["content"] == (
        "What is in these?\n[attachment-1: pdf, 3 pages] [attachment-2: image, 30x20]"
    )
    assert store.attachments(pdf.session_id, [pdf.id]) is None  # gone once answered


def test_files_are_dropped_even_when_the_model_is_offline():
    chat, _, store = make(FakeModel(unavailable=True))
    pdf = upload(chat)
    assert ask(chat, "Read this", pdf.session_id, [pdf.id]) == "offline"
    assert store.files == {}


def test_a_file_from_another_session_or_already_answered_makes_the_message_invalid():
    chat, model, _ = make()
    mine, theirs = upload(chat), upload(chat, ip="client-b")
    assert ask(chat, "Read this", mine.session_id, [theirs.id]) == "invalid"
    assert ask(chat, "Read this", mine.session_id, [mine.id]) == "ok"
    assert ask(chat, "Again", mine.session_id, [mine.id]) == "invalid"
    assert len(model.calls) == 1


def test_a_message_takes_3_files_at_most():
    chat, model, _ = make()
    sid = upload(chat).session_id
    ids = [upload(chat, sid=sid).id for _ in range(4)]
    assert (ask(chat, "Read these", sid, ids), model.calls) == ("invalid", [])


def test_a_message_with_files_neither_uses_nor_fills_the_answer_cache():
    cache = FakeCache()
    chat, _, _ = make(cache=cache)
    pdf = upload(chat)
    ask(chat, "What is this?", pdf.session_id, [pdf.id])
    assert cache.answers == {}


def test_an_upload_that_would_open_a_conversation_needs_the_browser_proof_too():
    chat, _, _ = make()
    chat.human = lambda token: token == "real-browser"
    assert chat.attach(session_id=None, client_key=IP, data=b"%PDF", human_token=None).status == "challenge"
    assert chat.attach(session_id=None, client_key=IP, data=b"%PDF", human_token="real-browser").status == "ok"
