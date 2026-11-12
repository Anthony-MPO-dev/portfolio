"""Anthropic API engine: the chat model through the official SDK (Claude Haiku 5.5, the author's choice of 12/11).

Responsibility: send the same prompt the worker sent (the fixed system prompt, cached; the conversation transcript;
a visitor's image as an image block before it), stream the text as it is written, and end with the parsed reply.
Thinking stays on at low effort (a chat from facts needs little); max_tokens is a safety net well above a long answer,
because thinking counts toward it. An API or transport error (the SDK lets raw httpx2 errors through once the stream
is read), a refusal or an answer cut at max_tokens is ModelUnavailable, even mid-stream, so the visitor sees "offline"
and never half an answer; after 3 failures in a row the API is skipped for 30 s (circuit breaker). Every billed
answer reports what it cost, also one cut short (the output guard blocked it, the visitor left, the stream broke): the
usage the API returned, or what the stream knew so far plus an estimate of the output, so the use case can close
the chat for the day at its budget. `connect` builds the client, so the provider stays in this module.
Public API: AnthropicModel (a ChatModel; AnthropicModel.connect), cost_usd, MODEL, LABEL.
Used by: app.main when ANTHROPIC_API_KEY is set, golden.test_live (the same engine for the golden set).
Depends on: anthropic (SDK), httpx2, app.adapters.prompt, app.breaker, app.ports.
Tests: tests/test_anthropic_model.py.
"""

import base64
import logging
from collections.abc import Callable, Iterator, Sequence
from types import SimpleNamespace

import anthropic
import httpx2

from app.adapters.prompt import parse_reply, transcript, without_contact
from app.breaker import CircuitBreaker, CircuitOpen
from app.ports import Attachment, ModelReply, ModelUnavailable, Turn

log = logging.getLogger(__name__)
MODEL, LABEL = "claude-haiku-5-5", "Haiku 5.5"
MAX_TOKENS = 4000  # thinking counts toward it; a normal answer uses a few hundred
PRICE = {"input": 0.10, "output": 0.50, "write": 0.125, "read": 0.01}  # US$ per million tokens, Claude Haiku 5.5
THINKING_GUESS = 300  # tokens, for an answer cut short before the API said what it used
FAILED = (anthropic.APIError, httpx2.HTTPError)


def cost_usd(usage) -> float:
    tokens = {
        "input": usage.input_tokens,
        "output": usage.output_tokens,
        "write": getattr(usage, "cache_creation_input_tokens", 0) or 0,
        "read": getattr(usage, "cache_read_input_tokens", 0) or 0,
    }
    return sum(tokens[k] * PRICE[k] for k in PRICE) / 1_000_000


def _so_far(stream, raw: str):
    """The usage of an answer cut short: the input the stream reported, and the output estimated from the text."""
    try:
        known = stream.current_message_snapshot.usage
    except Exception:  # nothing came back yet: nothing was billed
        return SimpleNamespace(input_tokens=0, output_tokens=0)
    return SimpleNamespace(
        input_tokens=known.input_tokens,
        output_tokens=max(known.output_tokens or 0, len(raw) // 3 + THINKING_GUESS),
        cache_read_input_tokens=getattr(known, "cache_read_input_tokens", 0),
        cache_creation_input_tokens=getattr(known, "cache_creation_input_tokens", 0),
    )


class AnthropicModel:
    def __init__(
        self,
        client,
        system: str,
        *,
        model: str = MODEL,
        on_cost: Callable[[float], None] | None = None,
        breaker: CircuitBreaker | None = None,
    ):
        self.client, self.model, self.on_cost = client, model, on_cost or (lambda usd: None)
        self.breaker = breaker or CircuitBreaker()
        self.system = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]

    @classmethod
    def connect(
        cls, api_key: str, system: str, *, workspace: str | None = None, timeout: float = 45, **kwargs
    ) -> "AnthropicModel":
        """The engine with its own client: a key not scoped to a workspace needs the workspace id."""
        headers = {"anthropic-workspace-id": workspace} if workspace else None
        client = anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=1, default_headers=headers)
        return cls(client, system, **kwargs)

    def stream(
        self, history: list[Turn], message: str, page_lang: str, attachments: Sequence[Attachment] = ()
    ) -> Iterator[str | ModelReply]:
        return without_contact(self._run(history, message, page_lang, attachments))

    def _open(self, content: list[dict]):
        manager = self.client.messages.stream(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=self.system,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": content}],
        )
        return manager, manager.__enter__()  # the request goes out here

    def _run(
        self, history: list[Turn], message: str, page_lang: str, attachments: Sequence[Attachment]
    ) -> Iterator[str | ModelReply]:
        content = [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64.b64encode(f.png).decode()}}
            for f in attachments
            if f.png
        ]  # fmt: skip
        content.append({"type": "text", "text": transcript(history, message, page_lang, attachments)})
        try:
            manager, stream = self.breaker.call(self._open, content)
        except CircuitOpen as error:
            raise ModelUnavailable("api skipped after repeated failures") from error
        except FAILED as error:
            log.warning("Anthropic API failed: %s", error.__class__.__name__)
            raise ModelUnavailable("api error") from error
        raw, usage = "", None
        try:
            for piece in stream.text_stream:
                raw += piece
                yield piece
            final = stream.get_final_message()
            usage = final.usage
        except FAILED as error:
            log.warning("Anthropic API failed mid-answer: %s", error.__class__.__name__)
            raise ModelUnavailable("api error") from error
        finally:  # also when the guard or a closed connection stops the answer at a yield
            self.on_cost(cost_usd(usage or _so_far(stream, raw)))
            manager.__exit__(None, None, None)
        if final.stop_reason != "end_turn":
            raise ModelUnavailable(f"stopped: {final.stop_reason}")
        yield parse_reply(raw)
