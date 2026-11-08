"""Chat use case: turn one visitor message into a result the page can show.

Responsibility: honour the off switch, apply the message, IP, turn and daily limits, keep the session strict (only
ids this server created), hold one answer at a time per session, log the redacted question, and stream the model's
answer as events: whole words only, each piece checked by the injected output guard on everything shown so far (a
hit ends the stream as "blocked", alerts Anthony and is never saved), the contact line turned into offer_contact,
and the turn saved once the answer completed clean. The lock is held until the stream ends.
Only saved exchanges count toward the conversation limit, so offline answers don't use it up, and a
conversation erased while the model was answering is not saved again.
Fixed notices (offline, limits) are the page's job: this module returns a status, never notice text.
Public API: ChatService.answer, ChatService.forget, Limits, ChatResult.
Used by: the /api/chat route.
Depends on: app.ports (ChatModel, SessionStore, QuestionLog), app.lang, app.redact.
Tests: tests/test_chat.py.
"""

import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Literal

from app.lang import page_lang as supported_lang
from app.adapters.prompt import CONTACT
from app.ports import ChatModel, ModelReply, ModelUnavailable, QuestionLog, QuestionLogUnavailable, SessionStore
from app.redact import redact

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Limits:
    max_chars: int = 500
    per_ip_hour: int = 20
    per_ip_day: int = 60
    turns: int = 20
    global_day: int = 300


Status = Literal["ok", "invalid", "rate_limited", "busy", "conversation_limit", "offline", "blocked"]


@dataclass(frozen=True)
class ChatResult:
    status: Status
    session_id: str | None = None
    reply: str | None = None
    offer_contact: bool = False
    events: Iterator[dict] | None = None  # an "ok" answer streams: delta events, then one done event


class ChatService:
    def __init__(
        self,
        model: ChatModel,
        store: SessionStore,
        log: QuestionLog,
        new_session_id: Callable[[], str],
        limits: Limits = Limits(),
        guard: Callable[[str], str | None] = lambda reply: None,
        alert: Callable[[str], None] = lambda reason: None,
    ):
        self.model = model
        self.store = store
        self.log = log
        self.new_session_id = new_session_id
        self.limits = limits
        self.guard = guard
        self.alert = alert

    def answer(self, *, session_id: str | None, client_key: str, message: str, page_lang: str) -> ChatResult:
        message = message.strip()
        if not message or len(message) > self.limits.max_chars:
            return ChatResult("invalid", session_id)
        if self.store.switched_off():
            return ChatResult("offline", session_id, offer_contact=True)

        per_hour, per_day = self.store.hit_ip(client_key)
        if per_hour > self.limits.per_ip_hour or per_day > self.limits.per_ip_day:
            return ChatResult("rate_limited", session_id)

        sid = self._strict_session(session_id)
        if not self.store.acquire_lock(sid):
            return ChatResult("busy", sid)
        owns_lock = True
        try:
            result = self._answer_locked(sid, message, supported_lang(page_lang))
            owns_lock = result.events is None  # a streaming answer releases the lock when its stream ends
            return result
        finally:
            if owns_lock:
                self.store.release_lock(sid)

    def forget(self, session_id: str | None) -> None:
        """The visitor's "erase conversation" button."""
        if session_id:
            self.store.delete_session(session_id)

    def _strict_session(self, sid: str | None) -> str:
        if sid and self.store.session_exists(sid):
            return sid
        sid = self.new_session_id()
        self.store.create_session(sid)
        return sid

    def _answer_locked(self, sid: str, message: str, lang: str) -> ChatResult:
        if self.store.turns(sid) >= self.limits.turns:
            return ChatResult("conversation_limit", sid)
        try:
            self.log.record(redact(message), lang)
        except QuestionLogUnavailable:
            pass  # the log only feeds the golden set; the visitor still gets an answer
        if self.store.hit_global() > self.limits.global_day:
            return ChatResult("offline", sid, offer_contact=True)
        return ChatResult("ok", sid, events=self._stream(sid, message, lang))

    def _stream(self, sid: str, message: str, lang: str) -> Iterator[dict]:
        """The answer as events: {"type": "delta", "text"} pieces, then one {"type": "done", "status",
        "offer_contact"}. Only whole words go out (the word still being written is held back), and the guard checks
        everything shown so far before each piece: a hit ends the stream as "blocked" and the page drops what it
        showed. The contact line never reaches the page. The turn is saved only when the answer completed clean."""
        shown, held, offer = "", "", False
        try:
            final = None
            try:
                for item in self.model.stream(self.store.history(sid), message, lang):
                    if isinstance(item, ModelReply):
                        final = item
                        break
                    held += item
                    if CONTACT in held:
                        offer, held = True, held.replace(CONTACT, "")
                    cut = max(held.rfind(" "), held.rfind("\n"))
                    if cut < 0:
                        continue
                    ready, held = held[: cut + 1], held[cut + 1 :]
                    if reason := self.guard(shown + ready):
                        yield self._blocked(reason)
                        return
                    shown += ready
                    yield {"type": "delta", "text": ready}
            except ModelUnavailable:
                final = None
            if final is None:
                yield {"type": "done", "status": "offline", "offer_contact": True}
                return
            rest = final.text[len(shown) :] if final.text.startswith(shown) else held.replace(CONTACT, "")
            text = (shown + rest).strip()
            if reason := self.guard(text):
                yield self._blocked(reason)
                return
            if rest.strip():
                yield {"type": "delta", "text": rest.rstrip()}
            if self.store.session_exists(sid):  # the visitor may have erased it while the model was answering
                self.store.append_turn(sid, message, text)
            yield {"type": "done", "status": "ok", "offer_contact": offer or final.offer_contact}
        finally:
            self.store.release_lock(sid)

    def _blocked(self, reason: str) -> dict:
        log.warning("reply blocked by the output guard: %s", reason)  # the reason only, never the text
        self.alert(f"output guard: {reason}")
        return {"type": "done", "status": "blocked", "offer_contact": True}
