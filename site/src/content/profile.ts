// Public facts shown on the site: a hand copy of knowledge/facts.md and the LinkedIn profile. Keep the wording,
// qualifiers included ("about", "as little as", "up to"), in sync with those sources.

export const profile = {
  name: "Anthony Muniz",
  role: "AI & Backend Engineer",
  headline: "I make LLM agents work with real customers, and I measure it.",
  lede: "Most AI agents look great in a demo and fall apart with real customers. I'm the engineer who finds out why and fixes it, with numbers to prove the fix worked.",
  open: "I'm open to remote backend and AI engineering roles with US and European teams. I also take small freelance projects through my company, Insight AI & Automation.",
  email: "anthonympodev@gmail.com",
  linkedin: "https://www.linkedin.com/in/anthony-mpo-dev",
  linkedinLabel: "linkedin.com/in/anthony-mpo-dev",
  github: "https://github.com/Anthony-MPO-dev",
  githubLabel: "github.com/Anthony-MPO-dev",
};

export type Case = { id: string; when: string; title: string; summary: string; numbers: string[]; stack: string };

export const cases: Case[] = [
  {
    id: "agent",
    when: "2026",
    title: "AI support agent for a B2B SaaS",
    summary:
      "It answers customers on WhatsApp, web chat and email. I shipped about 30 releases in 4 weeks, and replies got 3x faster.",
    numbers: ["3x faster replies", "~30 releases in 4 weeks", "13 of 23 test questions improved"],
    stack: "Python, LLMs, RAG, n8n, HubSpot",
  },
  {
    id: "credit",
    when: "2024 to 2026",
    title: "Credit analysis pipeline",
    summary: "I rebuilt a credit fund's manual credit analysis as Python services with queues and workers.",
    numbers: ["about 1 hour down to as little as 5 minutes", "about 10 to up to 100 operations a day", "5+ credit bureaus"],
    stack: "FastAPI, RabbitMQ, Celery, Redis",
  },
  {
    id: "logstream",
    when: "Side project",
    title: "LogStream",
    summary:
      "My first Go project. A sidecar agent streams logs over gRPC to a live dashboard, and healthmon blocks new requests to an external API once its error rate crosses a threshold.",
    numbers: ["Go and gRPC", "fsnotify and a ring buffer", "later retired for Grafana"],
    stack: "Go, gRPC, WebSocket, React",
  },
  {
    id: "rag",
    when: "2026",
    title: "RAG side projects",
    summary:
      "A PDF notes app and a resume generator on ChromaDB, plus Kai, my personal copilot, with embeddings and cosine similarity in numpy. The bug I remember: every restart wiped the vector index.",
    numbers: ["1,000-character chunks, 200 overlap", "duplicates dropped under 0.3 cosine distance", "100+ commits on the resume generator"],
    stack: "FastAPI, ChromaDB, Gemini embeddings, Celery",
  },
  {
    id: "tb",
    when: "2023 to 2025",
    title: "Tuberculosis surveillance research",
    summary:
      "Scrapers for Brazil's public health database feed a dashboard and a forecasting study. No single model won everywhere.",
    numbers: ["MAE 0.0205, the study's best result", "LSTM, ARIMA, DES and XGBoost compared", "67% of cases in men"],
    stack: "Python, Selenium, Pandas, Parquet",
  },
];
