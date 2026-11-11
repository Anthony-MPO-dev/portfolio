# Anthony Muniz: public facts

Single source of truth for the portfolio chatbot and the MCP server. Every line comes from Anthony's public LinkedIn
profile, his CV, or facts he approved for publishing. If something isn't here, the bot doesn't know it.

## At a glance

- AI and backend engineer. He makes LLM agents work with real customers, and he measures it.
- Based in Brazil (UTC-3), works remotely.
- 3+ years of professional Python experience, writing code since 2017.
- Languages: Portuguese (native), English (professional working proficiency).
- Open to remote full-time AI and backend engineering roles with US and European teams.
- Also takes on small freelance projects through his own company, Insight AI & Automation: n8n automations and AI
  chatbots.
- Core stack: Python, FastAPI, LLMs, RAG, Applied AI, Claude Code, LangChain, Agentic AI, Multi-Agent Systems, n8n,
  Machine Learning, XGBoost, RabbitMQ, Celery, Redis, Docker.

## Current work: an AI support agent for a B2B SaaS (since August 2026)

He works on contract through Insight AI & Automation. Right now that's an AI customer-support agent for a B2B SaaS,
live on WhatsApp, web chat and email. Around it he builds HubSpot workflows, n8n integrations and automated tests, and
he moved SharePoint document libraries to AWS S3.

- About 30 production releases in 4 weeks.
- Chat replies got 3x faster. A 45-second wait, meant to group split messages, was running on every single message.
  Now it's 15 seconds mid-conversation.
- He cleaned up the search behind the agent's answers. On 13 of 23 test questions it now finds a document it used to
  miss, and the right one ranks 1st or 2nd instead of 3rd. An audit of the knowledge base found 44 of 307 pages with
  dead links.
- The team's main dashboard metric swung 4x in 3 weeks while the bot hadn't changed at all. He replaced it with a
  resolution metric that holds up: no escalation, no reopening within 7 days, no human reply. It showed that 1 in 4
  "bot-resolved" chats actually had a human writing in them.
- He built an evaluation that caught an LLM judge calling a change a clear win when expert review rated it no better.
  The rule that stuck: use the judge's description, never its verdict. He also retired two automated detectors that
  had 80% false positives on good conversations.
- Tech: Python, TypeScript, LLMs, RAG, n8n, HubSpot, AWS S3, MongoDB, Claude Code.

The client's name, industry, customers and internal tools are confidential.

## Before: backend engineer at a credit fund (December 2024 to August 2026)

He rebuilt a credit fund's legacy low-code automations as Python and FastAPI services, test-first.

- Credit analysis used to take about an hour. His pipeline pulls from 5+ credit bureaus and gets it done in as fast
  as 5 minutes.
- Capacity went from about 10 to as many as 100 credit operations a day once he moved the heavy work to RabbitMQ and Celery
  workers. That's what let the team handle seasonal demand peaks.
- He set up Prometheus, Grafana, Loki and Tempo to trace every processing stage.
- Tech: Python, FastAPI, RabbitMQ, Celery, Redis, Docker, SQL Server.

A lesson from that kind of system: a FastAPI service once froze after the move to Celery and RabbitMQ, because
synchronous `.get()` calls blocked the worker threads.

## Research: tuberculosis surveillance (July 2023 to May 2025)

A part-time research fellowship at FAPEMAT, the Mato Grosso State Research Foundation, alongside his Computer Science
degree at UFMT, the Federal University of Mato Grosso. He built an automated surveillance platform for tuberculosis in
Mato Grosso, and it became his undergrad thesis: "an automated epidemiological surveillance platform for tuberculosis
in Mato Grosso, with time series forecasting."

- He built the pipeline end to end: Python and Selenium scrapers for Brazil's public health database (SINAN), Pandas
  to clean the data, Parquet for storage, and an interactive dashboard on top.
- He compared forecasting models: ARIMA and DES (statistical), XGBoost (machine learning) and LSTM (deep learning).
  No single one won. LSTM did best on tuberculosis overall, ARIMA on TB/HIV co-infection, and DES gave the study's best
  result (MAE 0.0205, on visceral leishmaniasis with HIV).
- The data showed 67% of tuberculosis cases in men, concentrated in Cuiabá and Várzea Grande.
- He later extended the platform to leprosy and leishmaniasis.
- Tech: Python, Selenium, Pandas, Parquet, XGBoost, LSTM, ARIMA, time series, geospatial analysis.

Earlier, from 2021 to 2022, he did in-person tech support and hardware repair.

## Side project: LogStream (2026)

Debugging his Python and Celery workers in production meant opening container after container and reading logs line
by line. He used that problem as an excuse to learn Go and gRPC in practice. It was his first Go project.

- Agent in Go: watches log files with fsnotify and streams them over gRPC, with a ring buffer.
- Server in Go: stores logs as JSONL per service per day, with SQLite and WebSocket pub/sub.
- Dashboard in React and TypeScript, with live logs.
- healthmon: watches the error rate of the external APIs the workers depend on. Past a configurable threshold it
  blocks new requests to that service, and it reopens on its own once the service is stable again. He already had
  retries with exponential backoff and a cache, but new requests kept hitting a service that was already down.
- He later retired it and moved production to Grafana, with Loki for logs and Tempo for traces. Once he needed traces,
  retention and alerting, maintaining his own tool stopped making sense.
- The architecture is his. He used Claude Code for parts of the implementation, like any other tool.
- Code: github.com/Anthony-MPO-dev/Observer_agent

## Side project: LinkedIn publishing pipeline (running since October 2026)

Python, n8n, PostgreSQL, Telegram and LinkedIn APIs, and headless Claude Code. Posts wait in a PostgreSQL queue (SKIP
LOCKED claims, idempotent upserts) until he approves them in a Telegram bot, then n8n publishes them on schedule. The
AI drafting jobs read strangers' comments, so they run with file access only: no shell, no web. That keeps a prompt
injection from reaching anything.

## Side projects with RAG (two on ChromaDB, Kai without it)

- **PDF notes app.** FastAPI, Gemini embeddings, ChromaDB, Celery, Redis and PostgreSQL.
  - Chunks of 1,000 characters with 200 of overlap.
  - Before indexing, each new chunk is compared with what's already stored and dropped if the cosine distance is below
    0.3, so the same passage isn't indexed twice.
  - All users share one collection. Every vector carries a `user_id`, and all 4 vector searches filter by it.
  - ChromaDB is pinned to 0.4.24 so the existing vector data isn't lost.
  - A bug he fixed: the migration marker lived inside the Docker image, so every new container ran the migration
    again and wiped the vector index on every restart.
- **Resume generator.** More than 100 commits. One ChromaDB collection per user, built for fewer than 100 users.
  - Chunks split by heading (H2, H3), and CSV rows turned into "key: value" lines before embedding.
  - The user's own data is the only source of facts the agent that writes the resume can use. So a chunk from another
    user would pass as valid evidence: an isolation bug doesn't throw an error, it produces a wrong resume.
- **Kai, a personal copilot.** Doesn't use ChromaDB. Conversation memory with `gemini-embedding-001` and cosine
  similarity in NumPy. It indexes each turn instead of sending the whole conversation with every question.

## Insight AI & Automation (freelance)

His own company. He automates manual work for mid-size companies and enterprise teams, in the US and Europe. Most projects are one of two things:

- an n8n workflow that moves data between HubSpot, Google Sheets, Gmail and WhatsApp;
- an AI chatbot that answers from the client's own documents and hands off to a human.

Fixed scope, fixed price, async, remote only. He quotes after seeing the task. This chatbot is a live demo of the
second kind. To start, a client sends the task they'd like to stop doing by hand.

## How he works

- Python backends that stay up under load: FastAPI, Celery, RabbitMQ, and observability he actually uses.
- LLM work past the prompt: RAG, evaluation checked against human reviewers, rollouts with a rollback trigger.
- He ships fast with AI coding tools, and the architecture is his.

## Education

- B.Sc. in Computer Science, UFMT (Federal University of Mato Grosso), 2020 to 2025.
- Technical course in Computer Science, IFRO (Federal Institute of Rondônia), 2017 to 2019.
- Databricks Fundamentals, Databricks Academy, October 2026.

## Contact

- Email: anthonympodev@gmail.com
- LinkedIn: linkedin.com/in/anthony-mpo-dev
- GitHub: github.com/Anthony-MPO-dev
- The contact form in this chat sends a message straight to Anthony.

## What the bot doesn't share

- The current client's name, industry, customers or internal tools.
- Salary, compensation or hourly rates.
- Anthony's phone number. The bot doesn't have it.
- Anything not written in this file. The bot says it doesn't know and offers the contact form.
