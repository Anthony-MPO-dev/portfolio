"""Anthropic API engine (off by default): the request it sends and how it reads, or gives up on, the answer."""

from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from app.adapters.anthropic_model import AnthropicModel
from app.adapters.prompt import REPLY_SCHEMA, transcript
from app.ports import ModelReply, ModelUnavailable

HISTORY = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "Hello!"}]


def text(t: str):
    return SimpleNamespace(type="text", text=t)


class FakeClient:
    """Stands in for anthropic.Anthropic: records the request, answers with the given blocks or raises."""

    def __init__(self, blocks=(), stop_reason="end_turn", error: Exception | None = None):
        self.calls: list[dict] = []
        self.blocks, self.stop_reason, self.error = list(blocks), stop_reason, error
        self.messages = self

    def create(self, **request):
        self.calls.append(request)
        if self.error:
            raise self.error
        return SimpleNamespace(content=self.blocks, stop_reason=self.stop_reason)


def test_sends_the_cached_system_prompt_the_transcript_and_the_reply_schema():
    client = FakeClient([text('{"reply": "Hi", "offer_contact": false}')])
    AnthropicModel(client, "SYSTEM", model="claude-haiku-5-5").reply(HISTORY, "Who is he?", "pt")
    (request,) = client.calls
    assert request["model"] == "claude-haiku-5-5"
    assert request["system"] == [{"type": "text", "text": "SYSTEM", "cache_control": {"type": "ephemeral"}}]
    assert request["messages"] == [{"role": "user", "content": transcript(HISTORY, "Who is he?", "pt")}]
    assert request["output_config"] == {"format": {"type": "json_schema", "schema": REPLY_SCHEMA}}
    assert request["max_tokens"] > 0


def test_reads_the_text_block_after_any_other_block():
    thinking = SimpleNamespace(type="thinking", thinking="...")
    client = FakeClient([thinking, text('{"reply": "Talk to Anthony.", "offer_contact": true}')])
    assert AnthropicModel(client, "S").reply([], "hire him", "en") == ModelReply("Talk to Anthony.", True)


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
def test_a_refused_or_cut_answer_is_unavailable_never_shown(stop_reason):
    client = FakeClient([text('{"reply": "Anthony is a back')], stop_reason=stop_reason)
    with pytest.raises(ModelUnavailable):
        AnthropicModel(client, "S").reply([], "q", "en")


def test_an_api_error_is_unavailable():
    error = anthropic.APITimeoutError(request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages"))
    with pytest.raises(ModelUnavailable):
        AnthropicModel(FakeClient(error=error), "S").reply([], "q", "en")


def test_no_text_is_unavailable():
    with pytest.raises(ModelUnavailable):
        AnthropicModel(FakeClient([]), "S").reply([], "q", "en")
