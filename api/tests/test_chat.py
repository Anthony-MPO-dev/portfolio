"""Chat use case: what a visitor gets back for each message, under the limits, session rules and offline cases."""

import pytest

from app.ports import ModelReply
from app.services.chat import ChatService, Limits
from tests.fakes import FakeModel, FakeStore

IP = "client-a"


def make(model: FakeModel | None = None, limits: Limits = Limits()):
    model = model or FakeModel()
    store = FakeStore()
    ids = (f"sid-{n}" for n in range(1, 1000))
    chat = ChatService(model=model, store=store, new_session_id=lambda: next(ids), limits=limits)
    return chat, model, store


def ask(chat: ChatService, message: str, sid: str | None = None, ip: str = IP, lang: str = "en"):
    return chat.answer(session_id=sid, client_key=ip, message=message, page_lang=lang)


def test_new_visitor_gets_a_session_and_the_model_reply():
    chat, _, _ = make(FakeModel(ModelReply("Hi, I'm Anthony's assistant.", offer_contact=False)))
    result = ask(chat, "hello")
    assert (result.status, result.reply, result.session_id) == ("ok", "Hi, I'm Anthony's assistant.", "sid-1")


def test_follow_up_message_sees_the_previous_turn():
    chat, model, _ = make()
    first = ask(chat, "Who is Anthony?")
    ask(chat, "And his stack?", sid=first.session_id)
    assert model.calls[-1].history == [
        {"role": "user", "content": "Who is Anthony?"},
        {"role": "assistant", "content": "reply 1"},
    ]


def test_session_id_the_server_never_created_is_replaced():
    chat, model, _ = make()
    result = ask(chat, "hello", sid="forged-id")
    assert (result.session_id, model.calls[-1].history) == ("sid-1", [])


@pytest.mark.parametrize("message", ["", "   ", "x" * 501])
def test_empty_or_too_long_message_is_rejected_without_calling_the_model(message):
    chat, model, _ = make()
    assert (ask(chat, message).status, model.calls) == ("invalid", [])


def test_message_at_the_size_limit_is_accepted():
    chat, _, _ = make()
    assert ask(chat, "x" * 500).status == "ok"


def test_ip_over_the_hourly_limit_is_rate_limited():
    chat, _, _ = make(limits=Limits(per_ip_hour=2))
    assert [ask(chat, "hi").status for _ in range(3)] == ["ok", "ok", "rate_limited"]


def test_ip_over_the_daily_limit_is_rate_limited():
    chat, _, _ = make(limits=Limits(per_ip_hour=10, per_ip_day=2))
    assert [ask(chat, "hi").status for _ in range(3)] == ["ok", "ok", "rate_limited"]


def test_one_ip_over_the_limit_does_not_block_other_visitors():
    chat, _, _ = make(limits=Limits(per_ip_hour=1))
    ask(chat, "hi", ip="client-a")
    assert ask(chat, "hi", ip="client-b").status == "ok"


def test_global_daily_cap_takes_the_bot_offline_and_offers_contact():
    chat, model, _ = make(limits=Limits(global_day=1))
    ask(chat, "hi", ip="client-a")
    result = ask(chat, "hi", ip="client-b")
    assert (result.status, result.offer_contact, len(model.calls)) == ("offline", True, 1)


def test_conversation_over_the_turn_limit_must_start_over():
    chat, _, _ = make(limits=Limits(turns=2))
    sid = ask(chat, "1").session_id
    ask(chat, "2", sid=sid)
    assert ask(chat, "3", sid=sid).status == "conversation_limit"


def test_model_unavailable_means_offline_with_contact_offer():
    chat, _, _ = make(FakeModel(unavailable=True))
    result = ask(chat, "hi")
    assert (result.status, result.reply, result.offer_contact) == ("offline", None, True)


def test_failed_turn_is_not_saved_and_does_not_block_the_next_message():
    model = FakeModel(unavailable=True)
    chat, _, _ = make(model)
    sid = ask(chat, "lost question").session_id
    model.unavailable = False
    result = ask(chat, "hi again", sid=sid)
    assert (result.status, model.calls[-1].history) == ("ok", [])


def test_second_message_while_the_first_is_being_answered_is_busy():
    chat, _, store = make()
    sid = ask(chat, "hi").session_id
    store.acquire_lock(sid)
    assert ask(chat, "again", sid=sid).status == "busy"


def test_page_language_reaches_the_model():
    chat, model, _ = make()
    ask(chat, "oi", lang="pt")
    assert model.calls[-1].page_lang == "pt"


def test_unsupported_page_language_falls_back_to_english():
    chat, model, _ = make()
    ask(chat, "bonjour", lang="fr")
    assert model.calls[-1].page_lang == "en"


def test_model_contact_signal_reaches_the_page():
    chat, _, _ = make(FakeModel(ModelReply("Sure, leave your details.", offer_contact=True)))
    assert ask(chat, "Can I talk to him?").offer_contact is True
