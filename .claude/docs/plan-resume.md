# Plan: resume and cover letter from the chat

Decided by Anthony on 22/11 (CLAUDE.md, "Currículo e carta pelo chat"): when a visitor asks for the resume, the chat
gives the resume and the cover letter together, as two PDF downloads with a progress percentage, and the page plays
the green rain when one finishes. Without a job post, the standard pair comes at once; with one, the pair is tailored.
Engine: the Anthropic API on his personal account (option a), about US$ 0.002 a pair.

## What the visitor sees

1. They ask for the resume (any wording, any language). The bot answers and the chat shows a panel under that
   answer: "Resume" and "Cover letter" buttons (the standard pair) and a field to paste the job post.
2. With a job post, "Tailor to this job" writes a new pair (a few seconds, with a status line); the buttons then
   download the tailored files.
3. Each button shows the download percentage; when a file finishes, the green rain falls over the whole page
   (reduced motion: no rain, only the "saved" line).

## How it works

- **Signal.** The model ends an answer with a resume line, the way it ends one with the contact line today
  (`prompt.py`); the API turns it into `offer_resume` in the stream's `done` event. Golden cases cover it.
- **Base.** `knowledge/resume.yaml`, public: the approved bullets per role (each with an id), skills, education,
  the standard summary and the letter's base paragraphs, all from the public profile. The private parts (city,
  address, the credit fund's name) come from the `RESUME_PRIVATE` env var on the server, never from the repo.
- **Tailoring.** `POST /api/resume` with the job post (up to 8,000 characters, treated as data, never as
  instructions). The model returns JSON: the bullet ids to keep, in order, per role; the skills order; a summary;
  the letter's paragraphs; the company and role it read. It never writes a bullet: the PDF prints the approved
  text of each id. A summary or letter with a number that is not in the facts, or with a forbidden term, is
  refused, and the visitor gets the standard pair.
- **Language.** The job post's language, English or Portuguese. Portuguese bullets come from the model's
  translation of the approved ones, accepted only when each keeps exactly the numbers of its source.
- **PDFs.** Rendered on the server with fpdf2 (pure Python, no system libraries) in a built-in font. The standard
  pair is rendered once per process and kept in memory.
- **Delivery.** The pair stays in Redis for 1 hour under a random token, readable only with the same chat
  session. `GET /api/resume/{token}/{resume|letter}.pdf` sends the bytes with `Content-Length`, so the page can
  show the percentage.
- **Limits.** Only inside an open chat session (it already passed Cloudflare's browser check). 3 tailored pairs
  per visitor a day, 50 a day for the site; the cost counts toward the chat's daily budget.
- **Copy to Anthony.** Each tailored pair sends an alert to his n8n (company, role, language), never the files
  or the job post. The n8n workflow learns a "resume" kind.
- **Privacy notice.** The job post is used for the answer and not stored.

## Tests (TDD)

- API: the resume line becomes `offer_resume`; the base loads and rejects a bullet without an id; the guard
  refuses a new number and a forbidden term; a model JSON with an unknown id or a missing field is refused; the
  limits; a token from another session gets nothing; the PDFs open and carry the approved text and the private
  location; the standard pair needs no model.
- Site: the reducer anchors the resume panel to its answer (like the contact form); the download reads the
  percentage from `Content-Length`; reduced motion skips the rain.
- Browser loop: the local build with a fake API (as for the chat fix), phone and desktop.
- Golden set: "send me his resume" in English and Portuguese offers the resume; the resume line never appears
  in the text.

## The 30 standards (padroes-de-projeto.md)

| # | State |
|---|---|
| 1 | not applicable: no images in the panel |
| 2 | done: a second click while a download runs reuses it; the standard pair is cached |
| 3 | not applicable: no search box |
| 4 | not applicable: no list |
| 5 | done: Cloudflare in front of the site |
| 6 | not applicable: one model call of a few seconds with a status line, as the chat does, no queue in the chat's path |
| 7 | not applicable: no database query |
| 8 | done: the site's Brotli/gzip; PDFs are already compressed |
| 9 | done: the standard pair needs no model; tailored pairs are not cached (each job post differs) |
| 10 | done: fpdf2 is the only new dependency, and it is used |
| 11 | done: the model call goes through the existing timeout and circuit breaker |
| 12 | not applicable: the output is a file, not text to read as it comes |
| 13 | done: the panel shows the status at once |
| 14 | not applicable: no images |
| 15 | done: both PDFs render from one model answer; downloads are independent |
| 16 | not applicable: no database query |
| 17 | done: the request is traced like the chat's |
| 18 | done: API and Redis on the same Easypanel network |
| 19 | done: the page stays prerendered; the panel is part of the chat |
| 20 | not applicable: no third-party script |
| 21 | done: the code lives in the chat's own chunk |
| 22 | not applicable: no long list |
| 23 | not applicable: no database |
| 24 | done: the existing Redis pool and API client |
| 25 | done: state in the chat reducer, stable keys |
| 26 | done: the site's hashed static files |
| 27 | done: the pair lives in Redis, not in one process |
| 28 | done: the site's own fonts; the PDF uses a built-in font |
| 29 | done: Web Vitals already measured |
| 30 | to do: phone mode and Slow 4G in the browser loop before delivery |
| 31 | not applicable: no messages to confirm |
