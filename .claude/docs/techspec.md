# Tech spec: portfolio chat API

Hexagonal, kept small: routes call use cases, use cases talk to ports, adapters implement ports. Decisions behind it
live in the author's project notes (2026-11-06).

## Mapa de Módulos

| Module | Layer | Responsibility | Public API | Tests |
|---|---|---|---|---|
| `api/app/ports.py` | ports | Model, session-store, lead, form-counter, question-log and worker-jobs contracts, and the data that crosses them | `Turn`, `ModelReply`, `ModelUnavailable`, `ChatModel`, `SessionStore`, `Lead`, `LeadUnavailable`, `LeadSink`, `FormCounter`, `QuestionLog`, `QuestionLogUnavailable`, `Job`, `WorkerJobs` | through the service and HTTP tests |
| `api/app/lang.py` | services | Supported page languages and the English fallback | `SUPPORTED`, `page_lang` | through the unsupported-language tests |
| `api/app/adapters/prompt.py` | adapters (shared by the model adapters) | System prompt (rules, the `<untrusted_content_policy>` block and the public facts, fixed so it can be cached, plus an optional per-process canary); the conversation as one JSON object inside `<conversation>`, with `<` and `>` escaped; the reply parser | `system_prompt`, `transcript`, `parse_reply`, `REPLY_SCHEMA` | `api/tests/test_prompt.py` |
| `api/app/redact.py` | services | Replaces e-mails and phone numbers (9+ digits) in a question before it's logged | `redact` | `api/tests/test_redact.py` |
| `api/app/output_guard.py` | services | The model's reply is hostile until checked: names the canary, a secret, a disk path, an email or phone that isn't Anthony's, a Markdown image or a link outside the allowlist | `check` | `api/tests/test_output_guard.py` |
| `api/app/services/chat.py` | services | Chat use case (and "erase conversation"): the off switch (`chat:off`), message, IP, turn and daily limits; strict session; one answer at a time per session; redacted question logged (a log failure never blocks the answer); model call; the reply through the injected output guard (a hit is `blocked`: never shown, never saved); turn saved. Returns a status, never notice text | `ChatService.answer`, `ChatService.forget`, `Limits`, `ChatResult` | `api/tests/test_chat.py` |
| `api/app/services/lead.py` | services | Lead use case: drops honeypot submissions, validates the form, caps valid forms per client per day (3), normalizes the LinkedIn URL, saves the lead, releases the WhatsApp number only to saved hiring leads | `LeadService.submit`, `LeadResult` | `api/tests/test_lead.py` |
| `api/app/adapters/redis_store.py` | adapters | `SessionStore` and `FormCounter` on Redis: `chat:m` (saved exchanges, 24 h absolute), `chat:h` (last 20 messages, 2 h sliding), `chat:lock` (90 s), per-client hour/day counters, daily site counter, daily form counter. Every key expires; UTC fixed windows | `RedisStore` | `api/tests/test_redis_store.py` (fakeredis; real local Redis with `REDIS_TEST_URL`) |
| `api/app/adapters/worker_queue.py` | adapters | `ChatModel` on Anthony's PC through Redis: pushes the job (system, transcript, schema, deadline) to `chat:jobs`, waits on `chat:res:{id}`; offline at once when no worker polled in 60 s (`chat:worker:seen`), on timeout or on an empty (failed) answer. Worker side: `next_job` skips jobs past their deadline, `finish` hands the raw answer back | `WorkerQueue.reply`, `WorkerQueue.next_job`, `WorkerQueue.finish` | `api/tests/test_worker_queue.py` |
| `api/worker/pc_worker.py` | separate program for the isolated chat worker (WSL distro or VM; outside `app/`, not in the API image) | Long-polls `/api/worker/next` with the token, runs `claude -p` hardened (`--restricted`, no built-in tools, `dontAsk` with only `StructuredOutput`, no MCP, hooks or commands, stream-json through stdin, a minimal environment without the worker token) and drops the answer with an ALERT when the init event or the stream shows any tool, MCP server, skill, command, installed plugin or permission denial | `command`, `child_env`, `stdin_message`, `unsafe`, `answer`, `serve`, `Api`, `run_claude`, `pick_claude`, `find_claude`, `main` | `api/tests/test_pc_worker.py` |
| `api/app/client_ip.py` | api | Visitor IP behind Cloudflare: `CF-Connecting-IP` trusted only when the peer is in Cloudflare's published ranges; otherwise the peer. `ip_source` says whose address was used (cloudflare, direct, shared, unknown) | `client_ip`, `ip_source`, `CLOUDFLARE_RANGES` | `api/tests/test_client_ip.py` |
| `api/app/http.py` | api | Routes only: `POST/DELETE /api/chat`, `POST /api/lead`, `GET /api/worker/next`, `POST /api/worker/jobs/{id}`, `GET /api/health` (with `ip`: how the caller's address was read, never the address). JSON only and same origin (Sec-Fetch-Site, Origin) on browser routes; `__Host-chat_sid` cookie set only for a new session; IP (through `client_ip`) turned into an HMAC; bearer token on worker routes (left out when the engine isn't the worker); no-store; no public docs | `create_app` | `api/tests/test_http.py` |
| `api/app/adapters/postgres.py` | adapters | `LeadSink` and `QuestionLog` on Postgres (`portfolio_leads` kept 12 months, `portfolio_questions` 30 days, deleted by `purge_expired`, which the API runs at startup and every 6 h); `forget_lead` deletes a person's leads on request (also a CLI); unreachable database raises the port's Unavailable | `ensure_schema`, `purge_expired`, `forget_lead`, `PostgresLeadSink`, `PostgresQuestionLog` | `api/tests/test_postgres.py` (local Postgres in `POSTGRES_TEST_URL`) |
| `api/app/adapters/lead_alert.py` | adapters | Lead saved first, then the alert to Anthony's personal n8n webhook (Telegram); a failed alert never undoes a saved lead | `SaveThenAlert`, `N8nAlert` | `api/tests/test_lead_alert.py` |
| `api/app/main.py` | composition | Reads the settings (no default secrets; secrets under 32 characters refused; only the `worker` engine for now), wires Redis store, worker queue, Postgres log and lead sink, n8n alert, and builds the app; the uvicorn factory also creates the tables and starts the retention purge | `build`, `app`, `ConfigError` | `api/tests/test_main.py` |
| `api/golden/grading.py` | evals (dev only, not in the API image) | Loads `evals/golden_set.yaml` (unknown key or repeated id is an error), plants a canary in the system prompt, grades one reply (expect groups, forbid regexes, secret terms, canary, `offer_contact`), reads `EVAL_FORBIDDEN_TERMS` (empty is an error) and masks those terms; a failure never repeats a secret term | `Case`, `load_cases`, `grade`, `plant_canary`, `forbidden_terms`, `mask` | `api/tests/test_golden.py` |
| `api/golden/test_live.py` | evals (dev only) | The live golden set: each case through the production path (prompt builder, the worker's isolated `claude -p`, reply parser), one model call per case. `uv run pytest golden` from `api/`, outside the unit run | pytest module | is the test |
| `api/tests/fakes.py` | tests | In-memory fakes of every port | `FakeModel`, `FakeStore`, `FakeLeadSink`, `FakeFormCounter`, `FakeQuestionLog` | n/a |

Planned, not built yet:

- Anthropic API model adapter (off), switched with the worker queue by an environment variable.

## Site (`site/src`)

React Router v7 in framework mode, prerendered to static HTML (`ssr: false`, `prerender: true`) and served by nginx.
Folders follow bulletproof-react: `app` (routes), `features`, `components`, `content`, `hooks`, `lib`, `styles`.
Identity: direction C (Archivo, big numbers, #fafaf7 / #0b0b0b / #e0322b), with technical labels in IBM Plex Mono.

| Module | Responsibility |
|---|---|
| `app/root.tsx` | HTML shell, fonts, and the boot script that applies the saved theme before paint |
| `app/routes.ts` | Route list: the home page (the `/pt/` pages come with the approved Portuguese texts) |
| `app/routes/home.tsx` + `home.css` | The one page, composed from the features: meta tags, header, hero, scenes, figures, work, Services, contact |
| `features/support-agent/*` | Scroll scenes of the support agent: the search fix (13 of 23) and the metric that lied, with their drawing styles |
| `features/credit-pipeline/*` | Scroll scene of the credit pipeline drawing itself, about 1 hour down to as fast as 5 minutes |
| `features/chat/chat.tsx` + `chat.css` | The chat: launcher in the corner, panel (a full page over the site on phones), transcript with line breaks kept, fixed notices, composer (500 characters; the attach button waits for the security work). `app/root.tsx` loads it lazily, and only in a build with `VITE_CHAT=1` |
| `features/chat/state.ts` | Pure reducer of the conversation: messages, waiting, notices by status, and where the contact form stands. Tests: `state.test.ts` |
| `features/chat/api.ts` | Client of `/api/chat` (POST, DELETE) and `/api/lead`; every failure becomes a status the page knows (offline, unavailable). Tests: `api.test.ts` (`npm test`, vitest) |
| `features/chat/lead-form.tsx` + `copy.ts` | Contact form (name, company, email, optional LinkedIn, Hiring or Project, honeypot) and the panel's fixed English text |
| `components/theme-toggle.tsx` + `.css` | Light or dark switch, remembered in `localStorage`; global.css picks its label |
| `content/profile.ts` | Public facts for the page's lists (profile, figures, work, Services), a hand copy of `knowledge/facts.md` and the approved LinkedIn texts. Each scene keeps its own caption next to its drawing |
| `hooks/use-reveal.ts` | IntersectionObserver fallback for browsers without scroll-driven animations |
| `lib/step.ts` | `step(i)`: an element's slice of its scene's scroll range |
| `styles/global.css` | Colour tokens for both themes, shared type, and the scene machinery (`view-timeline: --scene`; with reduced motion nothing moves or pins) |
