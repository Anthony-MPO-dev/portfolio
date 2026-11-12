"""Anthropic API engine: the chat model through the official SDK (Claude Haiku 5.5, the author's choice of 12/11).

Responsibility: send the same prompt the worker sent (the fixed system prompt, cached; the conversation transcript;
a visitor's image as an image block before it), stream the text as it is written, and end with the parsed reply.
Thinking stays on at low effort (a chat from facts needs little). An API error, a refusal or an answer cut at
max_tokens is ModelUnavailable, even mid-stream, so the visitor sees "offline" and never half an answer. Every
answer reports what it cost (from the usage the API returns), so the use case can close the chat for the day at
its budget. The client comes in configured (key, timeout, retries) from the composition.
Public API: AnthropicModel (a ChatModel), cost_usd.
Used by: app.main when ANTHROPIC_API_KEY is set.
Depends on: anthropic (SDK), app.adapters.prompt, app.ports.
Tests: tests/test_anthropic_model.py.
"""

import base64
import logging
from collections.abc import Callable, Iterator, Sequence

import anthropic

from app.adapters.prompt import parse_reply, transcript, without_contact
from app.ports import Attachment, ModelReply, ModelUnavailable, Turn

log = logging.getLogger(__name__)
MODEL = "claude-haiku-5-5"
MAX_TOKENS = 1500  # a safety net, far above a normal answer; it also bounds what one message can cost
PRICE = {"input": 0.10, "output": 0.50, "write": 0.125, "read": 0.01}  # US$ per million tokens, Claude Haiku 5.5


def cost_usd(usage) -> float:
    tokens = {
        "input": usage.input_tokens,
        "output": usage.output_tokens,
        "write": getattr(usage, "cache_creation_input_tokens", 0) or 0,
        "read": getattr(usage, "cache_read_input_tokens", 0) or 0,
    }
    return sum(tokens[k] * PRICE[k] for k in PRICE) / 1_000_000


class AnthropicModel:
    def __init__(self, client, system: str, *, model: str = MODEL, on_cost: Callable[[float], None] | None = None):
        self.client, self.model, self.on_cost = client, model, on_cost or (lambda usd: None)
        self.system = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]

    def stream(
        self, history: list[Turn], message: str, page_lang: str, attachments: Sequence[Attachment] = ()
    ) -> Iterator[str | ModelReply]:
        return without_contact(self._run(history, message, page_lang, attachments))

    def _run(
        self, history: list[Turn], message: str, page_lang: str, attachments: Sequence[Attachment]
    ) -> Iterator[str | ModelReply]:
        content = [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64.b64encode(f.png).decode()}}
            for f in attachments
            if f.png
        ]  # fmt: skip
        content.append({"type": "text", "text": transcript(history, message, page_lang, attachments)})
        raw = ""
        try:
            with self.client.messages.stream(
                model=self.model,
                max_tokens=MAX_TOKENS,
                system=self.system,
                output_config={"effort": "low"},
                messages=[{"role": "user", "content": content}],
            ) as stream:
                for piece in stream.text_stream:
                    raw += piece
                    yield piece
                final = stream.get_final_message()
        except anthropic.APIError as error:
            log.warning("Anthropic API failed: %s", error.__class__.__name__)
            raise ModelUnavailable("api error") from error
        self.on_cost(cost_usd(final.usage))
        if final.stop_reason != "end_turn":
            raise ModelUnavailable(f"stopped: {final.stop_reason}")
        yield parse_reply(raw)
