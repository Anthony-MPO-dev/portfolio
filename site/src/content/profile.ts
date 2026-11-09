// Public facts for the page's lists (profile, figures, work, Services): a hand copy of knowledge/facts.md and the
// approved LinkedIn texts. Each scroll scene keeps its own caption next to its drawing. Keep the wording, qualifiers
// included ("about", "as fast as", "up to"), in sync with those sources.

export const profile = {
  name: "Anthony Muniz",
  role: "AI & Backend Engineer",
  status: "Open to remote roles",
  based: "Based in Brazil, UTC-3",
  headline: "I make LLM agents work with real customers, and I measure it.",
  lede: "Most AI agents look great in a demo and fall apart with real customers. I'm the engineer who finds out why and fixes it, with numbers to prove the fix worked.",
  open: "I'm open to remote AI and backend engineering roles with US and European teams. I also take on small freelance projects through my company, Insight AI & Automation.",
  email: "anthonympodev@gmail.com",
  linkedin: "https://www.linkedin.com/in/anthony-mpo-dev",
  github: "https://github.com/Anthony-MPO-dev",
};

export const figures = [
  {
    fig: "3x",
    text: "faster chat replies on the support agent. A 45-second wait meant for split messages ran on every message. Now it's 15 seconds mid-conversation.",
  },
  {
    fig: "0.0205",
    from: 1, // lower is better, so it counts down from here; a starting point for the animation, not a result
    text: "MAE, the best result of my research, from plain double exponential smoothing on visceral leishmaniasis with HIV. No single model won everywhere.",
  },
];

export const cases = [
  {
    id: "agent",
    when: "2026",
    title: "AI support agent for a B2B SaaS",
    summary:
      "It answers customers on WhatsApp, web chat and email. I shipped about 30 releases in 4 weeks, and replies got 3x faster.",
    stack: "Python, LLMs, RAG, n8n, HubSpot",
  },
  {
    id: "credit",
    when: "2024 to 2026",
    title: "Credit analysis pipeline",
    summary: "I rebuilt a credit fund's manual credit analysis as Python services with queues and workers.",
    stack: "FastAPI, RabbitMQ, Celery, Redis",
  },
  {
    id: "logstream",
    when: "Side project",
    title: "LogStream",
    summary:
      "My first Go project. A sidecar agent streams logs over gRPC to a live dashboard, and healthmon blocks new requests to an external API once its error rate crosses a threshold.",
    stack: "Go, gRPC, WebSocket, React",
  },
  {
    id: "rag",
    when: "2026",
    title: "RAG side projects",
    summary:
      "A PDF notes app and a resume generator on ChromaDB, plus Kai, my personal copilot, with embeddings and cosine similarity in NumPy. The bug I remember: every restart wiped the vector index.",
    stack: "FastAPI, ChromaDB, Gemini embeddings, Celery",
  },
  {
    id: "tb",
    when: "2023 to 2025",
    title: "Tuberculosis surveillance research",
    summary:
      "My undergrad thesis, on a FAPEMAT research fellowship. Scrapers for Brazil's public health database feed a dashboard and a forecasting study, later extended to leprosy and leishmaniasis.",
    stack: "Python, Selenium, Pandas, Parquet",
  },
];

// Services of Insight AI & Automation: the approved LinkedIn Services page, word for word.
export const services = {
  company: "Insight AI & Automation",
  lead: "I automate the manual work in small businesses.",
  offer:
    "Most projects are one of two things: an n8n workflow that moves data between HubSpot, Google Sheets, Gmail and WhatsApp, or an AI chatbot that answers from your own docs and hands off to a human.",
  proof:
    "One pipeline I built does in 5 minutes, at its fastest, what used to take an hour. I also run an AI support agent in production with 3x faster replies, so I know where bots break.",
  terms: "Fixed scope, fixed price, async.",
  cta: "Send me the task you'd like to stop doing by hand.",
};
