# Tech spec: portfolio chat API

Hexagonal, kept small: routes call use cases, use cases talk to ports, adapters implement ports. Decisions behind it
live in the author's project notes (2026-11-06).

## Mapa de Módulos

| Module | Layer | Responsibility | Public API | Tests |
|---|---|---|---|---|
| `api/app/ports.py` | ports | Model, session-store, lead, form-counter and question-log contracts, and the data that crosses them | `Turn`, `ModelReply`, `ModelUnavailable`, `ChatModel`, `SessionStore`, `Lead`, `LeadUnavailable`, `LeadSink`, `FormCounter`, `QuestionLog`, `QuestionLogUnavailable` | through the service tests |
| `api/app/lang.py` | services | Supported page languages and the English fallback | `SUPPORTED`, `page_lang` | through the unsupported-language tests |
| `api/app/redact.py` | services | Replaces e-mails and phone numbers (9+ digits) in a question before it's logged | `redact` | `api/tests/test_redact.py` |
| `api/app/services/chat.py` | services | Chat use case: message, IP, turn and daily limits; strict session; one answer at a time per session; redacted question logged (a log failure never blocks the answer); model call; turn saved. Returns a status, never notice text | `ChatService.answer`, `Limits`, `ChatResult` | `api/tests/test_chat.py` |
| `api/app/services/lead.py` | services | Lead use case: drops honeypot submissions, validates the form, caps valid forms per client per day (3), normalizes the LinkedIn URL, saves the lead, releases the WhatsApp number only to saved hiring leads | `LeadService.submit`, `LeadResult` | `api/tests/test_lead.py` |
| `api/tests/fakes.py` | tests | In-memory fakes of every port | `FakeModel`, `FakeStore`, `FakeLeadSink`, `FakeFormCounter`, `FakeQuestionLog` | n/a |

Planned, not built yet:

- Redis session store adapter (keys and TTLs: `chat:m`, `chat:h`, `chat:lock`, `chat:rl`, daily counter).
- Local worker model adapter (on) and Anthropic API model adapter (off), switched by an environment variable.
- Prompt builder from `knowledge/facts.md`, shared by both model adapters.
- Lead sink adapter (Postgres plus the n8n alert to Telegram).
- `/api/chat` and lead routes, cookie `__Host-chat_sid`, same-origin checks.

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
| `features/credit-pipeline/*` | Scroll scene of the credit pipeline drawing itself, about 1 hour down to as little as 5 minutes |
| `components/theme-toggle.tsx` + `.css` | Light or dark switch, remembered in `localStorage`; global.css picks its label |
| `content/profile.ts` | Public facts for the page's lists (profile, figures, work, Services), a hand copy of `knowledge/facts.md` and the approved LinkedIn texts. Each scene keeps its own caption next to its drawing |
| `hooks/use-reveal.ts` | IntersectionObserver fallback for browsers without scroll-driven animations |
| `lib/step.ts` | `step(i)`: an element's slice of its scene's scroll range |
| `styles/global.css` | Colour tokens for both themes, shared type, and the scene machinery (`view-timeline: --scene`; with reduced motion nothing moves or pins) |
