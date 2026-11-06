# Tech spec: portfolio chat API

Hexagonal, kept small: routes call use cases, use cases talk to ports, adapters implement ports. Decisions behind it
live in the author's project notes (2026-11-06).

## Mapa de Módulos

| Module | Layer | Responsibility | Public API | Tests |
|---|---|---|---|---|
| `api/app/ports.py` | ports | Model, session-store, lead, form-counter and question-log contracts, and the data that crosses them | `Turn`, `ModelReply`, `ModelUnavailable`, `ChatModel`, `SessionStore`, `Lead`, `LeadUnavailable`, `LeadSink`, `FormCounter`, `QuestionLog`, `QuestionLogUnavailable` | through the service tests |
| `api/app/lang.py` | services | Supported page languages and the English fallback | `SUPPORTED`, `page_lang` | through the unsupported-language tests |
| `api/app/prompt.py` | services | System prompt (rules plus the public facts, fixed so it can be cached), conversation transcript for single-prompt engines, visitor text escaped so it can't open or close prompt tags, reader of the `{reply, offer_contact}` answer (plain text accepted, empty reply means unavailable) | `system_prompt`, `transcript`, `parse_reply`, `REPLY_SCHEMA` | `api/tests/test_prompt.py` |
| `api/app/redact.py` | services | Replaces e-mails and phone numbers (9+ digits) in a question before it's logged | `redact` | `api/tests/test_redact.py` |
| `api/app/services/chat.py` | services | Chat use case: message, IP, turn and daily limits; strict session; one answer at a time per session; redacted question logged (a log failure never blocks the answer); model call; turn saved. Returns a status, never notice text | `ChatService.answer`, `Limits`, `ChatResult` | `api/tests/test_chat.py` |
| `api/app/services/lead.py` | services | Lead use case: drops honeypot submissions, validates the form, caps valid forms per client per day (3), normalizes the LinkedIn URL, saves the lead, releases the WhatsApp number only to saved hiring leads | `LeadService.submit`, `LeadResult` | `api/tests/test_lead.py` |
| `api/app/adapters/redis_store.py` | adapters | `SessionStore` and `FormCounter` on Redis: `chat:m` (24 h absolute), `chat:h` (last 20 messages, 2 h sliding), `chat:lock` (90 s), per-client hour/day counters, daily site counter, daily form counter. Every key expires; UTC fixed windows | `RedisStore` | `api/tests/test_redis_store.py` (fakeredis; real local Redis with `REDIS_TEST_URL`) |
| `api/tests/fakes.py` | tests | In-memory fakes of every port | `FakeModel`, `FakeStore`, `FakeLeadSink`, `FakeFormCounter`, `FakeQuestionLog` | n/a |

Planned, not built yet:

- Local worker model adapter (on) and Anthropic API model adapter (off), switched by an environment variable.
- Lead sink adapter (Postgres plus the n8n alert to Telegram).
- `/api/chat` and lead routes, cookie `__Host-chat_sid`, same-origin checks.
