"""Anthropic API engine: the chat model through the official SDK. Off by default (MODEL_ENGINE=anthropic turns it on).

Responsibility: send the same prompt the worker sends (the fixed system prompt, cached; the conversation transcript;
the reply JSON schema as structured output), read the text block with the shared parser, and turn every API error,
a refusal, an answer cut at max_tokens or an empty answer into ModelUnavailable, so the visitor sees "offline" and
never half an answer. The client comes in configured (key, timeout, retries) from the composition.
Public API: AnthropicModel (a ChatModel).
Used by: app.main when MODEL_ENGINE=anthropic (a personal-account key with a spending cap, per the author's rule).
Depends on: anthropic (SDK), app.adapters.prompt, app.ports.
Tests: tests/test_anthropic_model.py.
"""

import logging

import anthropic

from app.adapters.prompt import REPLY_SCHEMA, parse_reply, transcript
from app.ports import ModelReply, ModelUnavailable, Turn

log = logging.getLogger(__name__)
MAX_TOKENS = 1500  # replies are short; same cap as the worker, and it bounds the cost of one message


class AnthropicModel:
    def __init__(self, client: anthropic.Anthropic, system: str, *, model: str = "claude-haiku-5-5"):
        self.client, self.model = client, model
        self.system = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]

    def reply(self, history: list[Turn], message: str, page_lang: str) -> ModelReply:
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                system=self.system,
                messages=[{"role": "user", "content": transcript(history, message, page_lang)}],
                output_config={"format": {"type": "json_schema", "schema": REPLY_SCHEMA}},
            )
        except anthropic.APIError as error:
            log.warning("Anthropic API failed: %s", error.__class__.__name__)
            raise ModelUnavailable("api error") from error
        if response.stop_reason != "end_turn":
            raise ModelUnavailable(f"stopped: {response.stop_reason}")
        return parse_reply(next((b.text for b in response.content if b.type == "text"), ""))
