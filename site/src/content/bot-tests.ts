import type { Lang } from "@/lib/lang";

// Texts of the "How this bot is tested" section, in English and Portuguese. The figures come from
// content/bot-tests.json, a complete golden set run the author makes on his PC (ops/golden-report.ps1): never typed by
// hand. The questions and replies stay as they ran, in both versions of the page.
// Public API: botTests. Used by: features/bot-tests/bot-tests.tsx.

const en = {
  label: "How this bot is tested",
  passed: (date: string, model: string) => `questions passed in the run of ${date}, on Claude ${model}.`,
  text: (total: number) =>
    `I put these ${total} questions to the bot on my own machine. Some ask for facts about me. Others fish for a client's name or a salary, try to pull out the bot's instructions, or switch to Portuguese. Each one has its own check. One wrong answer and the run fails.`,
  groups: {
    facts: "Facts about me",
    facts_pt: "Facts, asked in Portuguese",
    contact: "Contact and WhatsApp",
    unknown: "Things it doesn't know",
    out_of_scope: "Off-topic requests",
    confidential: "Confidential questions",
    injection: "Prompt injection",
    language: "Language",
  } as Record<string, string>,
  pass: "passed",
  fail: "failed",
  failed: "Failed:",
  attacks: "A few attacks it refused",
  note: "I only keep replies that went through the secret check. Secret terms are masked and long replies are cut. The terms themselves stay on my machine, never in this public repository.",
};

const pt: typeof en = {
  label: "Como este bot é testado",
  passed: (date: string, model: string) => `perguntas aprovadas na rodada de ${date}, no Claude ${model}.`,
  text: (total: number) =>
    `Fiz estas ${total} perguntas ao bot na minha própria máquina. Algumas pedem fatos sobre mim. Outras tentam arrancar o nome de um cliente ou um salário, tentam extrair as instruções do bot ou mudam para o português. Cada uma tem a sua checagem. Uma resposta errada e a rodada falha.`,
  groups: {
    facts: "Fatos sobre mim",
    facts_pt: "Fatos, perguntados em português",
    contact: "Contato e WhatsApp",
    unknown: "O que ele não sabe",
    out_of_scope: "Pedidos fora do assunto",
    confidential: "Perguntas confidenciais",
    injection: "Prompt injection",
    language: "Idioma",
  },
  pass: "aprovada",
  fail: "reprovada",
  failed: "Reprovadas:",
  attacks: "Alguns ataques que ele recusou",
  note: "Só guardo as respostas que passaram pela checagem de segredos. Os termos secretos aparecem mascarados e as respostas longas são cortadas. Os termos em si ficam na minha máquina, nunca neste repositório público.",
};

export const botTests: Record<Lang, typeof en> = { en, pt };
