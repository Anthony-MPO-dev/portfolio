"""In-memory fakes for the system boundaries: the model and the session store (Redis in production)."""

import re
from collections import Counter
from dataclasses import dataclass

from app.ports import (
    Attachment,
    Lead,
    LeadUnavailable,
    ModelReply,
    ModelUnavailable,
    QuestionLogUnavailable,
    Turn,
)


class FakeFormCounter:
    """Counts forms per client for the day, like the Redis counter."""

    def __init__(self):
        self.today: Counter[str] = Counter()

    def hit_form(self, client_key: str) -> int:
        self.today[client_key] += 1
        return self.today[client_key]


class FakeQuestionLog:
    """Keeps (question, page_lang) pairs, or raises like a database that is down."""

    def __init__(self, down: bool = False):
        self.down = down
        self.records: list[tuple[str, str]] = []

    def record(self, question: str, page_lang: str) -> None:
        if self.down:
            raise QuestionLogUnavailable()
        self.records.append((question, page_lang))


class FakeLeadSink:
    """Keeps saved leads in a list, or raises LeadUnavailable like a database or webhook that is down."""

    def __init__(self, down: bool = False):
        self.down = down
        self.saved: list[Lead] = []

    def save(self, lead: Lead) -> None:
        if self.down:
            raise LeadUnavailable()
        self.saved.append(lead)


@dataclass
class ModelCall:
    history: list[Turn]
    message: str
    page_lang: str
    attachments: list[Attachment]


class FakeModel:
    """Streams a scripted reply (or "reply N") in pieces, or raises ModelUnavailable like a worker that is offline;
    `pieces` scripts the exact chunks and `fail_after` drops the worker after that many."""

    def __init__(self, reply: ModelReply | None = None, unavailable: bool = False, during=None, pieces=None,
                 fail_after: int | None = None):  # fmt: skip
        self.scripted = reply
        self.unavailable = unavailable
        self.during = during  # called while "answering", to simulate what happens meanwhile
        self.pieces, self.fail_after = pieces, fail_after
        self.calls: list[ModelCall] = []

    def stream(self, history: list[Turn], message: str, page_lang: str, attachments=()):
        self.calls.append(ModelCall(list(history), message, page_lang, list(attachments)))
        if self.during:
            self.during()
        if self.unavailable:
            raise ModelUnavailable()
        final = self.scripted or ModelReply(f"reply {len(self.calls)}", offer_contact=False)
        pieces = self.pieces if self.pieces is not None else re.findall(r"\S+\s*", final.text)
        for n, piece in enumerate(pieces):
            if self.fail_after is not None and n == self.fail_after:
                raise ModelUnavailable("worker dropped mid-answer")
            yield piece
        yield final


class FakeStore:
    """Same contract as the Redis store, kept in dictionaries. No expiry: TTLs are the adapter's job."""

    def __init__(self):
        self.turn_counts: dict[str, int] = {}
        self.spent = 0.0
        self.histories: dict[str, list[Turn]] = {}
        self.locks: set[str] = set()
        self.ip_hour: Counter[str] = Counter()
        self.ip_day: Counter[str] = Counter()
        self.uploads: Counter[str] = Counter()
        self.global_day = 0
        self.off = False
        self.files: dict[tuple[str, str], Attachment] = {}
        self.file_counts: Counter[str] = Counter()
        self.files_off = False

    def switched_off(self) -> bool:
        return self.off

    def session_exists(self, sid: str) -> bool:
        return sid in self.turn_counts

    def create_session(self, sid: str) -> None:
        self.turn_counts.setdefault(sid, 0)

    def turns(self, sid: str) -> int:
        return self.turn_counts.get(sid, 0)

    def hit_ip(self, client_key: str) -> tuple[int, int]:
        self.ip_hour[client_key] += 1
        self.ip_day[client_key] += 1
        return self.ip_hour[client_key], self.ip_day[client_key]

    def hit_uploads(self, client_key: str) -> tuple[int, int]:
        self.uploads[client_key] += 1
        return self.uploads[client_key], self.uploads[client_key]

    def hit_global(self) -> int:
        self.global_day += 1
        return self.global_day

    def add_spend(self, usd: float) -> None:
        self.spent += usd

    def spend_today(self) -> float:
        return self.spent

    def acquire_lock(self, sid: str) -> bool:
        if sid in self.locks:
            return False
        self.locks.add(sid)
        return True

    def release_lock(self, sid: str) -> None:
        self.locks.discard(sid)

    def history(self, sid: str) -> list[Turn]:
        return list(self.histories.get(sid, []))

    def delete_session(self, sid: str) -> None:
        self.turn_counts.pop(sid, None)
        self.histories.pop(sid, None)
        self.locks.discard(sid)
        self.files = {key: f for key, f in self.files.items() if key[0] != sid}
        self.file_counts.pop(sid, None)

    def append_turn(self, sid: str, question: str, answer: str) -> None:
        self.histories.setdefault(sid, []).extend(
            [{"role": "user", "content": question}, {"role": "assistant", "content": answer}]
        )
        self.turn_counts[sid] = self.turn_counts.get(sid, 0) + 1

    def attachments_off(self) -> bool:
        return self.files_off

    def attachment_count(self, sid: str) -> int:
        return self.file_counts[sid]

    def save_attachment(self, sid: str, attachment: Attachment) -> str:
        self.file_counts[sid] += 1
        aid = f"file-{len(self.files) + 1}"
        self.files[(sid, aid)] = attachment
        return aid

    def attachments(self, sid: str, ids) -> list[Attachment] | None:
        found = [self.files.get((sid, aid)) for aid in ids]
        return None if None in found else found

    def drop_attachments(self, sid: str, ids) -> None:
        for aid in ids:
            self.files.pop((sid, aid), None)


class FakeCache:
    """Same contract as the Redis answer cache: answers by (page language, normalized question)."""

    def __init__(self, answers: dict | None = None):
        self.answers: dict[tuple[str, str], ModelReply] = dict(answers or {})

    def get(self, lang: str, question: str) -> ModelReply | None:
        return self.answers.get((lang, question))

    def put(self, lang: str, question: str, reply: ModelReply) -> None:
        self.answers[(lang, question)] = reply
