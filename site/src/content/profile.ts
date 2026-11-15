import type { Lang } from "@/lib/lang";

// Public facts for the home page's lists (profile, figures, work, Services), in English and Portuguese: a hand copy
// of knowledge/facts.md and the approved LinkedIn texts. The Portuguese is a faithful translation the author reviews
// (15/11). Each scroll scene keeps its own caption next to its drawing. Keep the wording, qualifiers included
// ("about", "as fast as", "up to"), in sync with those sources, in both languages.
// Public API: contact, home. Used by: app/routes/home.tsx, services.tsx, components/site-header.tsx, features/chat.

export const contact = {
  name: "Anthony Muniz",
  email: "anthonympodev@gmail.com",
  linkedin: "https://www.linkedin.com/in/anthony-mpo-dev",
  github: "https://github.com/Anthony-MPO-dev",
};

const en = {
  profile: {
    role: "AI & Backend Engineer",
    status: "Open to remote roles",
    based: "Based in Brazil, UTC-3",
    headline: "I make LLM agents work with real customers, and I measure it.",
    lede: "Most AI agents look great in a demo and fall apart with real customers. I'm the engineer who finds out why and fixes it, with numbers to prove the fix worked.",
    open: "I'm open to remote AI and backend engineering roles with US and European teams. I also take on small freelance projects through my company, Insight AI & Automation.",
  },
  labels: { results: "Results", work: "Work", services: "Services", contact: "Contact me", replay: "Play the animation again", hint: "replay" },
  figures: [
    {
      fig: "3x",
      text: "faster chat replies on the support agent. A 45-second wait meant for split messages ran on every message. Now it's 15 seconds mid-conversation.",
    },
    {
      fig: "0.0205",
      from: 1, // lower is better, so it counts down from here; a starting point for the animation, not a result
      text: "MAE, the best result of my research, from plain double exponential smoothing on visceral leishmaniasis with HIV. No single model won everywhere.",
    },
  ],
  cases: [
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
      when: "Side project, 2026",
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
  ],
  // Services of Insight AI & Automation: the approved LinkedIn Services page, word for word, except the lead, which
  // names the audience chosen for /services on 11/11 (the LinkedIn text gets the same line by the author's hand).
  services: {
    company: "Insight AI & Automation",
    lead: "I automate manual work for mid-size companies and enterprise teams.",
    offer:
      "Most projects are one of two things: an n8n workflow that moves data between HubSpot, Google Sheets, Gmail and WhatsApp, or an AI chatbot that answers from your own docs and hands off to a human.",
    proof:
      "One pipeline I built does in 5 minutes, at its fastest, what used to take an hour. I also run an AI support agent in production with 3x faster replies, so I know where bots break.",
    terms: "Fixed scope, fixed price, async.",
    cta: "Send me the task you'd like to stop doing by hand.",
    more: "See the services and the numbers behind them",
  },
};

const pt: typeof en = {
  profile: {
    role: "Engenheiro de IA e Backend",
    status: "Aberto a vagas remotas",
    based: "No Brasil, UTC-3",
    headline: "Faço agentes de LLM funcionarem com clientes reais, e meço isso.",
    lede: "A maioria dos agentes de IA brilha na demo e quebra com clientes reais. Sou o engenheiro que descobre o porquê e conserta, com números que provam que deu certo.",
    open: "Estou aberto a vagas remotas de engenharia de IA e backend em times dos EUA e da Europa. Também pego projetos freelance pequenos pela minha empresa, a Insight AI & Automation.",
  },
  labels: { results: "Resultados", work: "Projetos", services: "Serviços", contact: "Fale comigo", replay: "Tocar a animação de novo", hint: "repetir" },
  figures: [
    {
      fig: "3x",
      text: "respostas mais rápidas no chat do agente de atendimento. Uma espera de 45 segundos, pensada para mensagens mandadas em pedaços, rodava em toda mensagem. Agora são 15 segundos no meio da conversa.",
    },
    {
      fig: "0,0205",
      from: 1,
      text: "de MAE, o melhor resultado da minha pesquisa, com suavização exponencial dupla simples em leishmaniose visceral com HIV. Nenhum modelo sozinho ganhou em todos os casos.",
    },
  ],
  cases: [
    {
      id: "agent",
      when: "2026",
      title: "Agente de atendimento com IA para um SaaS B2B",
      summary:
        "Ele atende clientes no WhatsApp, no chat do site e por e-mail. Entreguei cerca de 30 versões em 4 semanas, e as respostas ficaram 3x mais rápidas.",
      stack: "Python, LLMs, RAG, n8n, HubSpot",
    },
    {
      id: "credit",
      when: "2024 a 2026",
      title: "Pipeline de análise de crédito",
      summary: "Refiz a análise de crédito manual de um fundo de crédito como serviços em Python, com filas e workers.",
      stack: "FastAPI, RabbitMQ, Celery, Redis",
    },
    {
      id: "logstream",
      when: "Projeto pessoal, 2026",
      title: "LogStream",
      summary:
        "Meu primeiro projeto em Go. Um agente sidecar manda os logs por gRPC para um painel ao vivo, e o healthmon bloqueia novas chamadas a uma API externa quando a taxa de erro dela passa de um limite.",
      stack: "Go, gRPC, WebSocket, React",
    },
    {
      id: "rag",
      when: "2026",
      title: "Projetos pessoais de RAG",
      summary:
        "Um app de notas a partir de PDFs e um gerador de currículo com ChromaDB, e o Kai, meu copiloto pessoal, com embeddings e similaridade de cosseno em NumPy. O bug que eu não esqueço: cada reinício apagava o índice de vetores.",
      stack: "FastAPI, ChromaDB, Gemini embeddings, Celery",
    },
    {
      id: "tb",
      when: "2023 a 2025",
      title: "Pesquisa de vigilância da tuberculose",
      summary:
        "Meu TCC, com bolsa de pesquisa da FAPEMAT. Scrapers da base pública de saúde do Brasil alimentam um painel e um estudo de previsão, depois estendidos para hanseníase e leishmaniose.",
      stack: "Python, Selenium, Pandas, Parquet",
    },
  ],
  services: {
    company: "Insight AI & Automation",
    lead: "Automatizo trabalho manual para empresas de médio porte e times de grandes empresas.",
    offer:
      "A maioria dos projetos é uma de duas coisas: um fluxo no n8n que leva dados entre HubSpot, Google Sheets, Gmail e WhatsApp, ou um chatbot de IA que responde a partir dos seus documentos e passa a conversa para uma pessoa.",
    proof:
      "Um pipeline que construí faz em 5 minutos, no melhor caso, o que levava uma hora. Também mantenho em produção um agente de atendimento com IA que responde 3x mais rápido, então sei onde os bots quebram.",
    terms: "Escopo fechado, preço fechado, trabalho assíncrono.",
    cta: "Me mande a tarefa que você quer parar de fazer à mão.",
    more: "Veja os serviços e os números por trás deles",
  },
};

export const home: Record<Lang, typeof en> = { en, pt };
