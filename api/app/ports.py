"""Ports of the chat API: the boundaries the use cases talk to.

Responsibility: define the model, session-store, lead, form-counter and question-log contracts, and the data
that crosses them.
Public API: Turn, ModelReply, ModelUnavailable, ChatModel, SessionStore, Lead, LeadUnavailable, LeadSink,
FormCounter, QuestionLog, QuestionLogUnavailable.
Used by: app.services.chat, app.services.lead. Adapters implement them (local worker model, Anthropic API
model, Redis store and counters, Postgres plus n8n lead sink, Postgres question log).
Depends on: nothing.
Tests: tests/test_chat.py and tests/test_lead.py, through the fakes in tests/fakes.py.
"""

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
    def reply(self, history: list[Turn], message: str, page_lang: str) -> ModelReply:
        """Answer `message` given the earlier turns. Raises ModelUnavailable when it can't."""
        ...


class SessionStore(Protocol):
    def session_exists(self, sid: str) -> bool:
        """True only for an id this server created that hasn't expired."""
        ...

    def create_session(self, sid: str) -> None: ...

    def count_turn(self, sid: str) -> int:
        """Add one turn to the session and return the new total."""
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

    def append_turn(self, sid: str, question: str, answer: str) -> None: ...

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
