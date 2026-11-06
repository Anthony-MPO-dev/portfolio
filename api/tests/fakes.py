"""In-memory fakes for the system boundaries: the model and the session store (Redis in production)."""

from collections import Counter
from dataclasses import dataclass

from app.ports import Lead, LeadUnavailable, ModelReply, ModelUnavailable, Turn


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


class FakeModel:
    """Returns a scripted reply (or "reply N"), or raises ModelUnavailable like a worker that is offline."""

    def __init__(self, reply: ModelReply | None = None, unavailable: bool = False):
        self.scripted = reply
        self.unavailable = unavailable
        self.calls: list[ModelCall] = []

    def reply(self, history: list[Turn], message: str, page_lang: str) -> ModelReply:
        self.calls.append(ModelCall(list(history), message, page_lang))
        if self.unavailable:
            raise ModelUnavailable()
        return self.scripted or ModelReply(f"reply {len(self.calls)}", offer_contact=False)


class FakeStore:
    """Same contract as the Redis store, kept in dictionaries. No expiry: TTLs are the adapter's job."""

    def __init__(self):
        self.turns: dict[str, int] = {}
        self.histories: dict[str, list[Turn]] = {}
        self.locks: set[str] = set()
        self.ip_hour: Counter[str] = Counter()
        self.ip_day: Counter[str] = Counter()
        self.global_day = 0

    def session_exists(self, sid: str) -> bool:
        return sid in self.turns

    def create_session(self, sid: str) -> None:
        self.turns.setdefault(sid, 0)

    def count_turn(self, sid: str) -> int:
        self.turns[sid] += 1
        return self.turns[sid]

    def hit_ip(self, client_key: str) -> tuple[int, int]:
        self.ip_hour[client_key] += 1
        self.ip_day[client_key] += 1
        return self.ip_hour[client_key], self.ip_day[client_key]

    def hit_global(self) -> int:
        self.global_day += 1
        return self.global_day

    def acquire_lock(self, sid: str) -> bool:
        if sid in self.locks:
            return False
        self.locks.add(sid)
        return True

    def release_lock(self, sid: str) -> None:
        self.locks.discard(sid)

    def history(self, sid: str) -> list[Turn]:
        return list(self.histories.get(sid, []))

    def append_turn(self, sid: str, question: str, answer: str) -> None:
        self.histories.setdefault(sid, []).extend(
            [{"role": "user", "content": question}, {"role": "assistant", "content": answer}]
        )
