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
    assert 0 < call["max_tokens"] <= 2000
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


def test_an_api_error_before_or_during_the_answer_is_offline():
    with pytest.raises(ModelUnavailable):
        run(AnthropicModel(FakeClient(connection_error()), "SYSTEM"))
    with pytest.raises(ModelUnavailable):
        run(AnthropicModel(FakeClient(FakeStream(["Half"], error=connection_error())), "SYSTEM"))


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
