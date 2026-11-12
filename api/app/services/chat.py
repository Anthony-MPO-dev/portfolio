"""Chat use case: turn one visitor message into a result the page can show.

Responsibility: honour the off switch, apply the message, IP (an hour, a day), turn and site-wide daily limits
(messages and the US$ the answers cost), ask a new conversation (message or upload) for the browser proof (Turnstile)
when the check is wired, keep the session strict (only
ids this server created), hold one answer at a time per session, log the redacted question, and stream the model's
answer as events: whole words only, each piece checked by the injected output guard on everything shown so far (a
hit ends the stream as "blocked", alerts Anthony and is never saved), the contact line turned into offer_contact,
and the turn saved once the answer completed clean. The lock is held until the stream ends.
Only saved exchanges count toward the conversation limit, so offline answers don't use it up, and a
conversation erased while the model was answering is not saved again.
Fixed notices (offline, limits) are the page's job: this module returns a status, never notice text.
Public API: ChatService.answer, ChatService.attach, ChatService.forget, Limits, ChatResult, AttachResult.
Used by: the /api/chat route.
Depends on: app.ports (ChatModel, SessionStore, QuestionLog, AnswerCache), app.lang, app.redact.
Tests: tests/test_chat.py, tests/test_chat_attachments.py.
"""

import logging
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from typing import Literal

from app.lang import page_lang as supported_lang
from app.ports import (
    AnswerCache,
    Attachment,
    AttachmentRejected,
    ChatModel,
    ModelReply,
    ModelUnavailable,
    QuestionLog,
    QuestionLogUnavailable,
    SessionStore,
)
from app.redact import redact

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Limits:
    max_chars: int = 500
    per_ip_hour: int = 20
    per_ip_day: int = 60
    turns: int = 20
    global_day: int = 300
    budget_day: float = 0.25  # US$ a day for the whole site, from what each answer cost (Anthropic API, 12/11)
    message_files: int = 3
    session_files: int = 10
    upload_ip_hour: int = 5  # apart from the messages: a message with 3 files still counts as one message
    upload_ip_day: int = 5  # files cost more tokens than text (author, 12/11)


Status = Literal[
    "ok", "invalid", "rate_limited", "daily_limit", "busy", "conversation_limit", "resting", "offline", "blocked",
    "challenge",
]


@dataclass(frozen=True)
class ChatResult:
    status: Status
    session_id: str | None = None
    reply: str | None = None
    offer_contact: bool = False
    events: Iterator[dict] | None = None  # an "ok" answer streams: delta events, then one done event


@dataclass(frozen=True)
class AttachResult:
    status: Literal["ok", "rejected", "rate_limited", "too_many", "offline", "challenge"]
    session_id: str | None = None
    id: str | None = None
    summary: str | None = None
    reason: str | None = None  # why a file was rejected: type, too_big, unreadable, no_text or busy


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
        cache: AnswerCache | None = None,
        convert: Callable[[bytes], Attachment] | None = None,
        human: Callable[[str | None], bool] | None = None,
    ):
        self.model = model
        self.store = store
        self.log = log
        self.new_session_id = new_session_id
        self.limits = limits
        self.guard = guard
        self.alert = alert
        self.cache = cache
        self.convert = convert
        self.human = human  # Turnstile: a new conversation needs a real browser's proof

    def attach(
        self, *, session_id: str | None, client_key: str, data: bytes, human_token: str | None = None
    ) -> AttachResult:
        """One uploaded file: converted in isolation and kept for this session until its answer ends. Uploads have
        their own IP limit, a conversation takes 10 at most, and the attachment switch turns them all away."""
        if self.convert is None or self.store.switched_off() or self.store.attachments_off():
            return AttachResult("offline", session_id)
        known = bool(session_id and self.store.session_exists(session_id))
        if not known and self.human and not self.human(human_token):  # before the count: a refusal costs nothing
            return AttachResult("challenge", session_id)
        if _over(self.store.hit_uploads(client_key), self.limits.upload_ip_hour, self.limits.upload_ip_day):
            return AttachResult("rate_limited", session_id)
        sid = session_id if known else self._new_session()
        if self.store.attachment_count(sid) >= self.limits.session_files:
            return AttachResult("too_many", sid)
        try:
            file = self.convert(data)
        except AttachmentRejected as refused:
            return AttachResult("rejected", sid, reason=str(refused))
        return AttachResult("ok", sid, id=self.store.save_attachment(sid, file), summary=file.summary)

    def answer(
        self,
        *,
        session_id: str | None,
        client_key: str,
        message: str,
        page_lang: str,
        attachments: Sequence[str] = (),
        human_token: str | None = None,
    ) -> ChatResult:
        message = message.strip()
        if not message or len(message) > self.limits.max_chars or len(attachments) > self.limits.message_files:
            return ChatResult("invalid", session_id)
        if self.store.switched_off():
            return ChatResult("offline", session_id, offer_contact=True)

        known = bool(session_id and self.store.session_exists(session_id))
        if not known and self.human and not self.human(human_token):  # before the count: a refusal costs nothing
            return ChatResult("challenge", session_id)
        hour, day = self.store.hit_ip(client_key)
        if day > self.limits.per_ip_day:  # the page says that's it for today
            return ChatResult("daily_limit", session_id)
        if hour > self.limits.per_ip_hour:
            return ChatResult("rate_limited", session_id)

        sid = session_id if known else self._new_session()
        if not self.store.acquire_lock(sid):
            return ChatResult("busy", sid)
        owns_lock = True
        try:
            result = self._answer_locked(sid, message, supported_lang(page_lang), list(attachments))
            owns_lock = result.events is None  # a streaming answer releases the lock when its stream ends
            return result
        finally:
            if owns_lock:
                self.store.release_lock(sid)

    def forget(self, session_id: str | None) -> None:
        """The visitor's "erase conversation" button."""
        if session_id:
            self.store.delete_session(session_id)

    def _new_session(self) -> str:
        """Strict sessions: only an id the server made and still holds goes on; anything else starts a new one."""
        sid = self.new_session_id()
        self.store.create_session(sid)
        return sid

    def _answer_locked(self, sid: str, message: str, lang: str, ids: list[str]) -> ChatResult:
        if self.store.turns(sid) >= self.limits.turns:
            return ChatResult("conversation_limit", sid)
        if ids and self.store.attachments_off():  # switched off after the upload: the files never reach the model
            self.store.drop_attachments(sid, ids)
            return ChatResult("offline", sid, offer_contact=True)
        files = self.store.attachments(sid, ids) if ids else []
        if files is None:  # another session's file, or one already answered or expired
            return ChatResult("invalid", sid)
        try:
            self.log.record(redact(message), lang)
        except QuestionLogUnavailable:
            pass  # the log only feeds the golden set; the visitor still gets an answer
        if self.store.hit_global() > self.limits.global_day or self.store.spend_today() >= self.limits.budget_day:
            return ChatResult("resting", sid, offer_contact=True)  # the whole site's share for today is used up
        return ChatResult("ok", sid, events=self._stream(sid, message, lang, ids, files))

    def _stream(self, sid: str, message: str, lang: str, ids: list[str], files: list[Attachment]) -> Iterator[dict]:
        """The answer as events: {"type": "delta", "text"} pieces, then one {"type": "done", "status",
        "offer_contact"}. Only whole words go out (the word still being written is held back), and the guard checks
        everything shown so far before each piece: a hit ends the stream as "blocked" and the page drops what it
        showed. Whether to offer the contact form comes with the final reply. The turn is saved only when the
        answer completed clean.
        A conversation's first question is answered from the cache when it can be, through the same guard, and a
        clean first answer from the model fills it (standards item 9). Files go to the model, the history keeps one
        line for each, and they are dropped when the stream ends, whatever the outcome."""
        shown, held = "", ""
        try:
            final = None
            history = self.store.history(sid)
            question = _same_question(message) if self.cache and not history and not files else None
            cached = self.cache.get(lang, question) if question else None
            source = iter([cached.text, cached]) if cached else self.model.stream(history, message, lang, files)
            try:
                for item in source:
                    if isinstance(item, ModelReply):
                        final = item
                        break
                    held += item
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
            rest = final.text[len(shown) :] if final.text.startswith(shown) else held
            text = (shown + rest).strip()
            if reason := self.guard(text):
                yield self._blocked(reason)
                return
            if rest.strip():
                yield {"type": "delta", "text": rest.rstrip()}
            if self.store.session_exists(sid):  # the visitor may have erased it while the model was answering
                lines = " ".join(f"[attachment-{n}: {f.summary}]" for n, f in enumerate(files, 1))
                self.store.append_turn(sid, f"{message}\n{lines}" if lines else message, text)
            if question and not cached:
                self.cache.put(lang, question, ModelReply(text, final.offer_contact))
            yield {"type": "done", "status": "ok", "offer_contact": final.offer_contact}
        finally:
            self.store.release_lock(sid)
            if ids:
                self.store.drop_attachments(sid, ids)

    def _blocked(self, reason: str) -> dict:
        log.warning("reply blocked by the output guard: %s", reason)  # the reason only, never the text
        self.alert(f"output guard: {reason}")
        return {"type": "done", "status": "blocked", "offer_contact": True}


def _over(counts: tuple[int, int], hour: int, day: int) -> bool:
    return counts[0] > hour or counts[1] > day


def _same_question(message: str) -> str:
    """What makes two first questions the same: case, spacing and the closing punctuation don't count."""
    return " ".join(message.split()).rstrip("?!. ").casefold()
