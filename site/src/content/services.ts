import type { Lang } from "@/lib/lang";

// Texts and figures of the /services page, in English and Portuguese (a faithful translation the author reviews,
// 15/11). The author's results come from knowledge/facts.md and content/profile.ts; the market figures from
// .claude/docs/research/automation-ai-value.md, each one read on the publisher's own page or PDF and worded as the
// source words it. Vendor-commissioned studies say so on the page. Nothing here is estimated: the only chart that
// changes is the calculator's, and it runs on the visitor's numbers. The sources keep their own (English) titles; on
// the Portuguese page the counts the site adds to them are in Brazilian format.
// Public API: servicesPage, Source. Used by: app/routes/services.tsx, features/services/*.

export type Source = { name: string; url: string };

const SOURCES = {
  stall: [
    {
      name: "IBM CEO Study, 2025 (2,000 CEOs)",
      url: "https://newsroom.ibm.com/2025-05-06-ibm-study-ceos-double-down-on-ai-while-navigating-enterprise-hurdles",
    },
    {
      name: "Deloitte, State of AI in the Enterprise, 2026",
      url: "https://www.deloitte.com/us/en/about/press-room/state-of-ai-report-2026.html",
    },
  ],
  blockers: [
    {
      name: "BCG, Where's the Value in AI?, 2024 (1,000 executives)",
      url: "https://www.bcg.com/press/24october2024-ai-adoption-in-2024-74-of-companies-struggle-to-achieve-and-scale-value",
    },
  ],
  payoff: [
    { name: "Forrester TEI for Microsoft, 2024", url: "https://tei.forrester.com/go/microsoft/powerautomatetei" },
    {
      name: "Forrester TEI for SS&C Blue Prism, 2024",
      url: "https://tei.forrester.com/go/sscblueprism/IntelligentAutomation/",
    },
    {
      name: "Deloitte, State of Generative AI, Q4 report, 2025",
      url: "https://www.deloitte.com/content/dam/assets-shared/docs/about/2025/quarter-4.pdf",
    },
  ],
} satisfies Record<string, Source[]>;

const en = {
  meta: { title: "Services" },
  intro: {
    label: "Services: Insight AI & Automation",
    title: "Most AI projects stall between the demo and production. I get them into production and measure what changes.",
    who: "I work with mid-size companies and with teams inside large ones, in the US and Europe.",
    sources: "Sources:",
  },
  stall: {
    aria: "Most AI stalls",
    kicker: "01 / the stall",
    lead: "Only",
    value: 25,
    squares: (n: number) => `${n} of 100 squares lit`,
    text: "of AI initiatives gave CEOs the return they expected.",
    also: "And only 25% of companies have moved 40% or more of their AI pilots into production.",
    sources: SOURCES.stall,
  },
  blockers: {
    aria: "Why it stalls",
    kicker: "02 / why",
    parts: [
      { label: "People and process", value: 70 },
      { label: "Technology", value: 20 },
      { label: "The algorithm", value: 10 },
    ],
    text: "The blocker is rarely the model. About 70% of what holds AI back is people and process, and only 10% is the algorithm. That's where most of my work goes.",
    sources: SOURCES.blockers,
  },
  payoff: {
    aria: "When it ships, it pays back",
    kicker: "03 / the payoff",
    studies: [
      { label: "Power Automate", roi: 248 },
      { label: "Blue Prism", roi: 330 },
    ],
    roiLabel: "ROI,",
    text: "Once automation reaches production, it can pay for itself fast. In two Forrester models paid for by the vendors, payback came in under 6 months. And 74% of leaders say their most advanced generative AI initiative meets or exceeds their ROI expectations.",
    note: "Return over three years, risk-adjusted, for a model company built from interviews with each vendor's customers.",
    sources: SOURCES.payoff,
  },
  // Each service's drawing (offer.tsx, by id) has a caption with the same figures as its proof, and the words it
  // draws (before, then after).
  offer: {
    aria: "Services",
    kicker: "04 / what I put in production",
    services: [
      {
        id: "automation",
        name: "Automation",
        line: "I build n8n workflows and Python services that move data between HubSpot, Google Sheets, Gmail and WhatsApp, so nobody on your team copies it by hand.",
        proof: "A credit analysis I rebuilt went from about an hour to as fast as 5 minutes.",
        caption: "1 hour → as fast as 5 min",
        words: ["copy", "paste", "check", "email", "file"],
      },
      {
        id: "agents",
        name: "AI agents and skills",
        line: "I build support agents that answer from your own documents and hand off to a person when they can't. I also set up agents and skills your team uses every day.",
        proof: "My support agent in production replies 3x faster: 15 seconds mid-conversation instead of 45.",
        caption: "replies 3x faster, 45 s → 15 s",
        words: ["question", "your docs", "answer", "a person"],
      },
      {
        id: "data",
        name: "Data and dashboards",
        line: "I build pipelines that collect your numbers, dashboards that show them, and forecasts when they're worth it.",
        proof: "My research pipeline turned Brazil's public health database into a dashboard and a forecasting study.",
        caption: "scattered numbers → one dashboard",
        words: [] as string[],
      },
      {
        id: "software",
        name: "Custom software",
        line: "I write backend services and APIs for one job, and I test and measure them before you rely on them.",
        proof:
          "Moving the heavy work to queues and workers raised capacity from about 10 to as many as 100 operations a day.",
        caption: "about 10 → as many as 100 operations a day",
        words: [] as string[],
      },
    ],
  },
  calculator: {
    aria: "Your numbers",
    kicker: "05 / your numbers",
    example: "The numbers below are only an example. Put in yours.",
    people: "People who do the task",
    hours: "Hours a week each one spends on it",
    cut: "Share of that time automation could cut",
    cutNote: "Your guess. My credit pipeline cut an hour of work to 5 minutes at its fastest.",
    rate: "Optional: what one of those hours costs you",
    ratePlaceholder: "e.g. 50",
    result: "hours back a year",
    fullTime: (n: string, people: number) =>
      `About ${n} full-time ${people === 1 ? "person" : "people"} (40 hours a week) free for other work.`,
    worth: (n: string) => `Worth about ${n} a year at that cost.`,
    chart: (weeks: number) => `Hours back, first year (${weeks} working weeks)`,
    months: ["Month 1", "Month 12"],
    chartLabel: (n: string) => `Hours back piling up over 12 months, reaching ${n}.`,
    monthTitle: (m: number, n: string) => `Month ${m}: ${n} hours`,
    terms: "Fixed scope, fixed price, async.",
    cta: "Send me the task you'd like to stop doing by hand.",
  },
};

const pt: typeof en = {
  meta: { title: "Serviços" },
  intro: {
    label: "Serviços: Insight AI & Automation",
    title: "A maioria dos projetos de IA trava entre a demo e a produção. Eu coloco em produção e meço o que muda.",
    who: "Trabalho com empresas de médio porte e com times dentro de grandes empresas, nos EUA e na Europa.",
    sources: "Fontes:",
  },
  stall: {
    aria: "A maioria da IA trava",
    kicker: "01 / a trava",
    lead: "Só",
    value: 25,
    squares: (n: number) => `${n} de 100 quadrados acesos`,
    text: "das iniciativas de IA deram aos CEOs o retorno que eles esperavam.",
    also: "E só 25% das empresas levaram 40% ou mais dos seus pilotos de IA para a produção.",
    sources: [{ ...SOURCES.stall[0], name: "IBM CEO Study, 2025 (2.000 CEOs)" }, SOURCES.stall[1]],
  },
  blockers: {
    aria: "Por que trava",
    kicker: "02 / por quê",
    parts: [
      { label: "Pessoas e processos", value: 70 },
      { label: "Tecnologia", value: 20 },
      { label: "O algoritmo", value: 10 },
    ],
    text: "O que trava raramente é o modelo. Cerca de 70% do que segura a IA são pessoas e processos, e só 10% é o algoritmo. É aí que está a maior parte do meu trabalho.",
    sources: [{ ...SOURCES.blockers[0], name: "BCG, Where's the Value in AI?, 2024 (1.000 executivos)" }],
  },
  payoff: {
    aria: "Em produção, ela se paga",
    kicker: "03 / o retorno",
    studies: [
      { label: "Power Automate", roi: 248 },
      { label: "Blue Prism", roi: 330 },
    ],
    roiLabel: "ROI,",
    text: "Quando a automação chega à produção, ela pode se pagar rápido. Em dois modelos da Forrester pagos pelos próprios fornecedores, o investimento se pagou em menos de 6 meses. E 74% dos líderes dizem que a iniciativa de IA generativa mais avançada deles atinge ou supera o ROI esperado.",
    note: "Retorno em três anos, ajustado ao risco, de uma empresa modelo montada a partir de entrevistas com clientes de cada fornecedor.",
    sources: SOURCES.payoff,
  },
  offer: {
    aria: "Serviços",
    kicker: "04 / o que eu coloco em produção",
    services: [
      {
        id: "automation",
        name: "Automação",
        line: "Construo fluxos no n8n e serviços em Python que levam dados entre HubSpot, Google Sheets, Gmail e WhatsApp, para ninguém do seu time copiar à mão.",
        proof: "Uma análise de crédito que refiz caiu de cerca de uma hora para 5 minutos no melhor caso.",
        caption: "1 hora → 5 min no melhor caso",
        words: ["copiar", "colar", "checar", "e-mail", "arquivar"],
      },
      {
        id: "agents",
        name: "Agentes de IA e skills",
        line: "Construo agentes de atendimento que respondem a partir dos seus documentos e passam para uma pessoa quando não conseguem resolver. Também monto agentes e skills que o seu time usa todo dia.",
        proof: "Meu agente de atendimento em produção responde 3x mais rápido: 15 segundos no meio da conversa, em vez de 45.",
        caption: "respostas 3x mais rápidas, 45 s → 15 s",
        words: ["pergunta", "seus docs", "resposta", "pessoa"],
      },
      {
        id: "data",
        name: "Dados e painéis",
        line: "Construo pipelines que coletam os seus números, painéis que os mostram e previsões quando valem a pena.",
        proof: "O pipeline da minha pesquisa transformou a base pública de saúde do Brasil num painel e num estudo de previsão.",
        caption: "números espalhados → um painel",
        words: [],
      },
      {
        id: "software",
        name: "Software sob medida",
        line: "Escrevo serviços de backend e APIs para uma tarefa, e testo e meço antes de você depender deles.",
        proof:
          "Passar o trabalho pesado para filas e workers aumentou a capacidade de cerca de 10 para até 100 operações por dia.",
        caption: "cerca de 10 → até 100 operações por dia",
        words: [],
      },
    ],
  },
  calculator: {
    aria: "Os seus números",
    kicker: "05 / os seus números",
    example: "Os números abaixo são só um exemplo. Coloque os seus.",
    people: "Pessoas que fazem a tarefa",
    hours: "Horas por semana que cada uma gasta nela",
    cut: "Parte desse tempo que a automação pode cortar",
    cutNote: "Um palpite seu. Meu pipeline de crédito cortou uma hora de trabalho para 5 minutos no melhor caso.",
    rate: "Opcional: quanto custa uma dessas horas para você",
    ratePlaceholder: "ex.: 50",
    result: "horas de volta por ano",
    fullTime: (n: string, people: number) =>
      `Cerca de ${n} ${people < 2 ? "pessoa" : "pessoas"} em tempo integral (40 horas por semana) ${people < 2 ? "livre" : "livres"} para outro trabalho.`,
    worth: (n: string) => `Equivale a cerca de ${n} por ano, a esse custo.`,
    chart: (weeks: number) => `Horas de volta, primeiro ano (${weeks} semanas de trabalho)`,
    months: ["Mês 1", "Mês 12"],
    chartLabel: (n: string) => `Horas de volta se acumulando em 12 meses, até chegar a ${n}.`,
    monthTitle: (m: number, n: string) => `Mês ${m}: ${n} horas`,
    terms: "Escopo fechado, preço fechado, trabalho assíncrono.",
    cta: "Me mande a tarefa que você quer parar de fazer à mão.",
  },
};

export const servicesPage: Record<Lang, typeof en> = { en, pt };
