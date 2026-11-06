# Tech spec: portfolio chat API

Hexagonal, kept small: routes call use cases, use cases talk to ports, adapters implement ports. Decisions behind it
live in the author's project notes (2026-11-06).

## Mapa de Módulos

| Module | Layer | Responsibility | Public API | Tests |
|---|---|---|---|---|
| `api/app/ports.py` | ports | Model, session-store and lead contracts, and the data that crosses them | `Turn`, `ModelReply`, `ModelUnavailable`, `ChatModel`, `SessionStore`, `Lead`, `LeadUnavailable`, `LeadSink` | through `api/tests/test_chat.py`, `api/tests/test_lead.py` |
| `api/app/lang.py` | services | Supported page languages and the English fallback | `SUPPORTED`, `page_lang` | through the unsupported-language tests |
| `api/app/services/chat.py` | services | Chat use case: message, IP, turn and daily limits; strict session; one answer at a time per session; model call; turn saved. Returns a status, never notice text | `ChatService.answer`, `Limits`, `ChatResult` | `api/tests/test_chat.py` |
| `api/app/services/lead.py` | services | Lead use case: validates the form, normalizes the LinkedIn URL, saves the lead, releases the WhatsApp number only to saved hiring leads | `LeadService.submit`, `LeadResult` | `api/tests/test_lead.py` |
| `api/tests/fakes.py` | tests | In-memory fakes of the model, the store and the lead sink | `FakeModel`, `FakeStore`, `FakeLeadSink` | n/a |

Planned, not built yet:

- Redis session store adapter (keys and TTLs: `chat:m`, `chat:h`, `chat:lock`, `chat:rl`, daily counter).
- Local worker model adapter (on) and Anthropic API model adapter (off), switched by an environment variable.
- Prompt builder from `knowledge/facts.md`, shared by both model adapters.
- Lead sink adapter (Postgres plus the n8n alert to Telegram).
- `/api/chat` and lead routes, cookie `__Host-chat_sid`, same-origin checks.
