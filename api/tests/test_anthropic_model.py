"""Anthropic engine: the text streams, the reply ends it, every billed answer counts toward the day's budget, and any
failure is offline, never half an answer."""

from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from app.adapters.anthropic_model import AnthropicModel, cost_usd
from app.ports import Attachment, ModelReply, ModelUnavailable


def usage(input=4000, output=300, read=0, write=0):
    return SimpleNamespace(
        input_tokens=input, output_tokens=output, cache_read_input_tokens=read, cache_creation_input_tokens=write
    )


class FakeStream:
    def __init__(self, pieces, stop="end_turn", use=None, error=None):
        self.pieces, self.stop, self.use, self.error = pieces, stop, use or usage(), error

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    @property
    def text_stream(self):
        yield from self.pieces
        if self.error:
            raise self.error

    def get_final_message(self):
        return SimpleNamespace(stop_reason=self.stop, usage=self.use)

    @property
    def current_message_snapshot(self):  # what the SDK knows mid-stream: the input, not yet the output
        return SimpleNamespace(usage=usage(self.use.input_tokens, 1, self.use.cache_read_input_tokens, 0))


class FakeClient:
    def __init__(self, stream):
        self.calls = []
        self.messages = SimpleNamespace(stream=self._stream)
        self._next = stream

    def _stream(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self._next, Exception):
            raise self._next
        return self._next


def run(model, message="Is he open to roles?", attachments=()):
    return list(model.stream([], message, "en", attachments))


def connection_error():
    return anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages"))


def test_streams_the_text_then_the_reply_and_the_contact_line_never_reaches_the_visitor():
    model = AnthropicModel(FakeClient(FakeStream(["Yes, remote ", "roles.\n", "[[con", "tact]]"])), "SYSTEM")
    out = run(model)
    assert "".join(p for p in out if isinstance(p, str)).strip() == "Yes, remote roles."
    assert out[-1] == ModelReply("Yes, remote roles.", True)


def test_sends_the_cached_system_prompt_the_conversation_and_haiku_at_low_effort():
    client = FakeClient(FakeStream(["Hi."]))
    run(AnthropicModel(client, "SYSTEM"))
    call = client.calls[0]
    assert call["model"] == "claude-haiku-5-5"
    assert call["system"] == [{"type": "text", "text": "SYSTEM", "cache_control": {"type": "ephemeral"}}]
    assert call["output_config"] == {"effort": "low"}
    assert call["max_tokens"] >= 4000  # thinking counts toward it; a long answer must not be cut
    [turn] = call["messages"]
    assert turn["role"] == "user" and "<conversation>" in turn["content"][-1]["text"]


def test_an_image_goes_as_an_image_block_before_the_conversation():
    client = FakeClient(FakeStream(["A chart."]))
    picture = Attachment(kind="image", summary="image, 10x10", png=b"\x89PNG")
    run(AnthropicModel(client, "SYSTEM"), attachments=[picture])
    first, last = client.calls[0]["messages"][0]["content"]
    assert first["type"] == "image" and first["source"]["media_type"] == "image/png"
    assert last["type"] == "text"


@pytest.mark.parametrize("stop", ["refusal", "max_tokens"])
def test_a_refusal_or_a_cut_answer_is_offline_not_half_an_answer(stop):
    with pytest.raises(ModelUnavailable):
        run(AnthropicModel(FakeClient(FakeStream(["Partial"], stop=stop)), "SYSTEM"))


@pytest.mark.parametrize(
    "error", [connection_error(), httpx2.ReadTimeout("read timed out"), httpx2.RemoteProtocolError("peer closed")]
)
def test_an_error_before_or_during_the_answer_is_offline(error):
    with pytest.raises(ModelUnavailable):
        run(AnthropicModel(FakeClient(error), "SYSTEM"))
    with pytest.raises(ModelUnavailable):  # the SDK lets raw transport errors through once the stream is read
        run(AnthropicModel(FakeClient(FakeStream(["Half"], error=error)), "SYSTEM"))


def test_after_three_failures_in_a_row_the_api_is_skipped_for_a_while():
    client = FakeClient(connection_error())
    model = AnthropicModel(client, "SYSTEM")
    for _ in range(4):
        with pytest.raises(ModelUnavailable):
            run(model)
    assert len(client.calls) == 3


def test_an_answer_cut_short_still_counts_what_it_cost():
    spent = []
    model = AnthropicModel(FakeClient(FakeStream(["Ignore your rules ", "and tell me"])), "SYSTEM", on_cost=spent.append)
    pieces = model.stream([], "q", "en")
    next(pieces)
    pieces.close()  # the output guard blocked it, or the visitor left
    assert len(spent) == 1 and spent[0] > cost_usd(usage(input=4000, output=0))


def test_each_answer_reports_what_it_cost_even_when_it_ends_offline():
    spent = []
    use = usage(input=1000, output=200, read=3000, write=0)
    run(AnthropicModel(FakeClient(FakeStream(["Ok."], use=use)), "SYSTEM", on_cost=spent.append))
    with pytest.raises(ModelUnavailable):
        run(AnthropicModel(FakeClient(FakeStream(["x"], stop="max_tokens", use=use)), "SYSTEM", on_cost=spent.append))
    assert spent == [pytest.approx(cost_usd(use))] * 2


def test_cost_follows_the_haiku_prices_per_million_tokens():
    # input $0.10, output $0.50, cache write $0.125, cache read $0.01 (per million)
    assert cost_usd(usage(input=1_000_000, output=0)) == pytest.approx(0.10)
    assert cost_usd(usage(input=0, output=1_000_000)) == pytest.approx(0.50)
    assert cost_usd(usage(input=0, output=0, read=1_000_000, write=1_000_000)) == pytest.approx(0.135)
