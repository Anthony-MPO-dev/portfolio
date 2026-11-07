# Tech spec: portfolio chat API

Hexagonal, kept small: routes call use cases, use cases talk to ports, adapters implement ports. Decisions behind it
live in the author's project notes (2026-11-06).

## Mapa de Módulos

| Module | Layer | Responsibility | Public API | Tests |
|---|---|---|---|---|
| `api/app/ports.py` | ports | Model, session-store, lead, form-counter, question-log and worker-jobs contracts, and the data that crosses them | `Turn`, `ModelReply`, `ModelUnavailable`, `ChatModel`, `SessionStore`, `Lead`, `LeadUnavailable`, `LeadSink`, `FormCounter`, `QuestionLog`, `QuestionLogUnavailable`, `Job`, `WorkerJobs` | through the service and HTTP tests |
| `api/app/lang.py` | services | Supported page languages and the English fallback | `SUPPORTED`, `page_lang` | through the unsupported-language tests |
| `api/app/adapters/prompt.py` | adapters (shared by the model adapters) | System prompt (rules plus the public facts, fixed so it can be cached), conversation transcript for single-prompt engines, visitor text escaped so it can't open or close prompt tags, reader of the `{reply, offer_contact}` answer (plain text accepted, empty reply means unavailable) | `system_prompt`, `transcript`, `parse_reply`, `REPLY_SCHEMA` | `api/tests/test_prompt.py` |
| `api/app/redact.py` | services | Replaces e-mails and phone numbers (9+ digits) in a question before it's logged | `redact` | `api/tests/test_redact.py` |
| `api/app/services/chat.py` | services | Chat use case (and "erase conversation"): message, IP, turn and daily limits; strict session; one answer at a time per session; redacted question logged (a log failure never blocks the answer); model call; turn saved. Returns a status, never notice text | `ChatService.answer`, `ChatService.forget`, `Limits`, `ChatResult` | `api/tests/test_chat.py` |
| `api/app/services/lead.py` | services | Lead use case: drops honeypot submissions, validates the form, caps valid forms per client per day (3), normalizes the LinkedIn URL, saves the lead, releases the WhatsApp number only to saved hiring leads | `LeadService.submit`, `LeadResult` | `api/tests/test_lead.py` |
| `api/app/adapters/redis_store.py` | adapters | `SessionStore` and `FormCounter` on Redis: `chat:m` (saved exchanges, 24 h absolute), `chat:h` (last 20 messages, 2 h sliding), `chat:lock` (90 s), per-client hour/day counters, daily site counter, daily form counter. Every key expires; UTC fixed windows | `RedisStore` | `api/tests/test_redis_store.py` (fakeredis; real local Redis with `REDIS_TEST_URL`) |
| `api/app/adapters/worker_queue.py` | adapters | `ChatModel` on Anthony's PC through Redis: pushes the job (system, transcript, schema, deadline) to `chat:jobs`, waits on `chat:res:{id}`; offline at once when no worker polled in 60 s (`chat:worker:seen`), on timeout or on an empty (failed) answer. Worker side: `next_job` skips jobs past their deadline, `finish` hands the raw answer back | `WorkerQueue.reply`, `WorkerQueue.next_job`, `WorkerQueue.finish` | `api/tests/test_worker_queue.py` |
| `api/worker/pc_worker.py` | separate program on Anthony's PC (outside `app/`, not in the API image) | Long-polls `/api/worker/next` with the token, runs `claude -p` isolated (`--safe-mode`, `--tools ""`, `--strict-mcp-config`, no session, empty folder, job's system prompt and schema, visitor text on stdin), hands the raw answer back; any failure hands back an empty answer; backoff on network errors. Standard library only | `command`, `answer`, `serve`, `Api`, `run_claude`, `find_claude`, `log`, `main` | `api/tests/test_pc_worker.py` |
| `api/app/client_ip.py` | api | Visitor IP behind Cloudflare: `CF-Connecting-IP` trusted only when the peer is in Cloudflare's published ranges; otherwise the peer | `client_ip`, `CLOUDFLARE_RANGES` | `api/tests/test_client_ip.py` |
| `api/app/http.py` | api | Routes only: `POST/DELETE /api/chat`, `POST /api/lead`, `GET /api/worker/next`, `POST /api/worker/jobs/{id}`, `GET /api/health`. JSON only and same origin (Sec-Fetch-Site, Origin) on browser routes; `__Host-chat_sid` cookie set only for a new session; IP (through `client_ip`) turned into an HMAC; bearer token on worker routes (left out when the engine isn't the worker); no-store; no public docs | `create_app` | `api/tests/test_http.py` |
| `api/app/adapters/postgres.py` | adapters | `LeadSink` and `QuestionLog` on Postgres (`portfolio_leads` kept 12 months, `portfolio_questions` 30 days; each write deletes what is past retention); unreachable database raises the port's Unavailable | `ensure_schema`, `PostgresLeadSink`, `PostgresQuestionLog` | `api/tests/test_postgres.py` (local Postgres in `POSTGRES_TEST_URL`) |
| `api/app/adapters/lead_alert.py` | adapters | Lead saved first, then the alert to Anthony's personal n8n webhook (Telegram); a failed alert never undoes a saved lead | `SaveThenAlert`, `N8nAlert` | `api/tests/test_lead_alert.py` |
| `api/app/main.py` | composition | Reads the settings (no default secrets; secrets under 32 characters refused; only the `worker` engine for now), wires Redis store, worker queue, Postgres log and lead sink, n8n alert, and builds the app; the uvicorn factory also creates the tables | `build`, `app`, `ConfigError` | `api/tests/test_main.py` |
| `api/tests/fakes.py` | tests | In-memory fakes of every port | `FakeModel`, `FakeStore`, `FakeLeadSink`, `FakeFormCounter`, `FakeQuestionLog` | n/a |

Planned, not built yet:

- Anthropic API model adapter (off), switched with the worker queue by an environment variable.
