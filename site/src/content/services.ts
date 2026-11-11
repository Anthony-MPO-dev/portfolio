// Texts and figures of the /services page. The author's results come from knowledge/facts.md and content/profile.ts;
// the market figures from .claude/docs/research/automation-ai-value.md, each one read on the publisher's own page or
// PDF. Vendor-commissioned studies say so on the page. Nothing here is estimated: the only chart that changes is the
// calculator's, and it runs on the visitor's numbers.

export const intro = {
  label: "Services: Insight AI & Automation",
  title: "Most AI projects stall between the demo and production. I get them into production and measure what changes.",
  who: "I work with mid-size companies and with teams inside large ones, in the US and Europe.",
};

type Source = { name: string; url: string };

export const stall = {
  kicker: "01 / the stall",
  value: 25,
  text: "of AI initiatives gave CEOs the return they expected.",
  also: "And only 25% of companies have moved 40% or more of their AI pilots into production.",
  sources: [
    {
      name: "IBM CEO Study, 2025 (2,000 CEOs)",
      url: "https://newsroom.ibm.com/2025-05-06-ibm-study-ceos-double-down-on-ai-while-navigating-enterprise-hurdles",
    },
    {
      name: "Deloitte, State of AI in the Enterprise, 2026",
      url: "https://www.deloitte.com/us/en/about/press-room/state-of-ai-report-2026.html",
    },
  ] satisfies Source[],
};

export const blockers = {
  kicker: "02 / why",
  parts: [
    { label: "People and process", value: 70 },
    { label: "Technology", value: 20 },
    { label: "The algorithm", value: 10 },
  ],
  text: "The blocker is rarely the model. About 70% of what holds AI back is people and process, and only 10% is the algorithm. That's where most of my work goes.",
  sources: [
    {
      name: "BCG, Where's the Value in AI?, 2024 (1,000 executives)",
      url: "https://www.bcg.com/press/24october2024-ai-adoption-in-2024-74-of-companies-struggle-to-achieve-and-scale-value",
    },
  ] satisfies Source[],
};

export const payoff = {
  kicker: "03 / the payoff",
  studies: [
    { label: "Power Automate", roi: "248%" },
    { label: "Blue Prism", roi: "330%" },
  ],
  text: "Once automation is in production, it pays for itself fast. Both studies found payback in under 6 months, and 74% of leaders say their most advanced AI initiative meets or beats its ROI target.",
  note: "Return over three years, risk-adjusted. Both studies were paid for by the vendors.",
  sources: [
    { name: "Forrester TEI for Microsoft, 2024", url: "https://tei.forrester.com/go/microsoft/powerautomatetei" },
    {
      name: "Forrester TEI for SS&C Blue Prism, 2024",
      url: "https://tei.forrester.com/go/sscblueprism/IntelligentAutomation/",
    },
    {
      name: "Deloitte, State of Generative AI, Q4 report, 2025",
      url: "https://www.deloitte.com/content/dam/assets-shared/docs/about/2025/quarter-4.pdf",
    },
  ] satisfies Source[],
};

export const offer = {
  kicker: "04 / what I put in production",
  services: [
    {
      id: "automation",
      name: "Automation",
      line: "I build n8n workflows and Python services that move data between HubSpot, Google Sheets, Gmail and WhatsApp, so nobody on your team copies it by hand.",
      proof: "A credit analysis I rebuilt went from about an hour to as fast as 5 minutes.",
    },
    {
      id: "agents",
      name: "AI agents and skills",
      line: "I build support agents that answer from your own documents and hand off to a person when they can't. I also set up agents and skills your team uses every day.",
      proof: "My support agent in production replies 3x faster: 15 seconds mid-conversation instead of 45.",
    },
    {
      id: "data",
      name: "Data and dashboards",
      line: "I build pipelines that collect your numbers, dashboards that show them, and forecasts when they're worth it.",
      proof: "My research pipeline turned Brazil's public health database into a dashboard and a forecasting study.",
    },
    {
      id: "software",
      name: "Custom software",
      line: "I write backend services and APIs for one job, and I test and measure them before you rely on them.",
      proof:
        "Moving the heavy work to queues and workers raised capacity from about 10 to as many as 100 operations a day.",
    },
  ],
};

export const calculator = {
  kicker: "05 / your numbers",
  people: "People who do the task",
  hours: "Hours a week each one spends on it",
  cut: "Share of that time automation could cut",
  cutNote: "Your guess. My credit pipeline cut an hour of work to 5 minutes at its fastest.",
  rate: "Optional: what one of those hours costs you",
  result: "hours back a year",
  chart: "Hours back, first year",
  terms: "Fixed scope, fixed price, async.",
  cta: "Send me the task you'd like to stop doing by hand.",
};
