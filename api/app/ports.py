"""Ports of the chat API: the boundaries the use cases talk to.

Responsibility: define the model, session-store, answer-cache, lead, form-counter and question-log contracts, and
the data that crosses them.
Public API: Turn, ModelReply, ModelUnavailable, ChatModel, SessionStore, AnswerCache, Lead, LeadUnavailable,
LeadSink, FormCounter, QuestionLog, QuestionLogUnavailable, Job, WorkerJobs.
Used by: app.services.chat, app.services.lead, app.http (WorkerJobs). Adapters implement them (the worker queue
model, Redis store, answer cache and counters, Postgres plus n8n lead sink, Postgres question log).
Depends on: nothing.
Tests: tests/test_chat.py and tests/test_lead.py, through the fakes in tests/fakes.py.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal, Protocol, TypedDict


class Turn(TypedDict):
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class ModelReply:
    text: str
    offer_contact: bool


class ModelUnavailable(Exception):
    """The model can't answer right now: worker offline, timeout or quota."""


class ChatModel(Protocol):
    def stream(self, history: list[Turn], message: str, page_lang: str) -> Iterator[str | ModelReply]:
        """Answer `message` given the earlier turns: yield text pieces as they are written, then the final
        ModelReply. Raises ModelUnavailable when it can't, even mid-stream."""
        ...


class AnswerCache(Protocol):
    """Clean answers to a conversation's first question, by page language and normalized question. The adapter
    keys them by prompt version too, so new facts never meet an old answer."""

    def get(self, lang: str, question: str) -> ModelReply | None: ...

    def put(self, lang: str, question: str, reply: ModelReply) -> None: ...


class SessionStore(Protocol):
    def switched_off(self) -> bool:
        """The operator's off switch (chat:off): the chat answers offline until it's gone."""
        ...

    def session_exists(self, sid: str) -> bool:
        """True only for an id this server created that hasn't expired."""
        ...

    def create_session(self, sid: str) -> None: ...

    def turns(self, sid: str) -> int:
        """How many exchanges the session has saved."""
        ...

    def hit_ip(self, client_key: str) -> tuple[int, int]:
        """Count one message for this client and return (messages this hour, messages today)."""
        ...

    def hit_global(self) -> int:
        """Count one message for the whole site and return the total for today."""
        ...

    def acquire_lock(self, sid: str) -> bool:
        """Take the session's answer lock. False when another answer is in progress."""
        ...

    def release_lock(self, sid: str) -> None: ...

    def history(self, sid: str) -> list[Turn]: ...

    def append_turn(self, sid: str, question: str, answer: str) -> None:
        """Save one exchange in the history and count it."""
        ...

    def delete_session(self, sid: str) -> None:
        """Erase everything stored about the session ("erase conversation")."""
        ...


@dataclass(frozen=True)
class Lead:
    name: str
    company: str
    email: str
    linkedin: str | None
    kind: Literal["hiring", "project"]
    page_lang: str


class LeadUnavailable(Exception):
    """The lead couldn't be stored or Anthony couldn't be alerted."""


class LeadSink(Protocol):
    def save(self, lead: Lead) -> None:
        """Store the lead and alert Anthony. Raises LeadUnavailable when it can't."""
        ...


class FormCounter(Protocol):
    def hit_form(self, client_key: str) -> int:
        """Count one valid form from this client and return today's total."""
        ...


class QuestionLogUnavailable(Exception):
    """The question log can't be written right now."""


class QuestionLog(Protocol):
    def record(self, question: str, page_lang: str) -> None:
        """Keep an already-redacted question for 30 days. Raises QuestionLogUnavailable when it can't."""
        ...


class Job(TypedDict):
    """One model request handed to the worker on Anthony's PC."""

    id: str
    system: str
    prompt: str
    deadline: float  # Unix time; past it, nobody is waiting


class WorkerJobs(Protocol):
    """The worker's side of the local-worker engine, behind the three worker routes."""

    def next_job(self, wait: int) -> Job | None: ...

    def chunk(self, job_id: str, text: str) -> None: ...

    def finish(self, job_id: str, raw: str) -> None: ...
