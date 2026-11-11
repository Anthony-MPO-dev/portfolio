// Texts of the "How this bot is tested" section. The figures come from content/bot-tests.json, the golden set run the
// author makes on his PC (ops/golden-report.ps1): never typed by hand.

export const botTests = {
  label: "How this bot is tested",
  passed: (date: string, model: string) =>
    `test questions passed on ${date}, each one a real reply from Claude ${model}.`,
  text: (total: number) =>
    `Before I deploy, I ask the bot ${total} questions on my own machine: facts about me, things it should refuse, prompt injection, and questions in Portuguese. If a reply names a confidential detail or leaks its instructions, the run fails.`,
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
  failed: "Failed:",
  attacks: "A few attacks it refused",
  note: "Replies are shown as the bot gave them, cut when long. Confidential terms are checked on my machine and never stored in this public repository.",
};
