// Texts of the "How this bot is tested" section. The figures come from content/bot-tests.json, a complete golden set
// run the author makes on his PC (ops/golden-report.ps1): never typed by hand.

export const botTests = {
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
