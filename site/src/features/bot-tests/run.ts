// The golden set run the page shows ("How this bot is tested"): content/bot-tests.json, written by the live run on
// the author's PC (api/golden/test_live.py with GOLDEN_REPORT). summarize counts the passes and groups the cases in
// the page's order, numbering them across the run so the squares light up one after another; showcase picks attacks
// the bot refused, only passing cases with a reply (failing replies never reach the JSON anyway).
// Public API: Case, Run, GROUP_ORDER, summarize, showcase. Used by features/bot-tests/bot-tests.tsx. Tests: run.test.ts.

export type Case = { id: string; group: string; q: string; passed: boolean; seconds: number; reply: string | null };
export type Run = { date: string; model: string; cases: Case[] };

export const GROUP_ORDER = [
  "facts",
  "facts_pt",
  "contact",
  "unknown",
  "out_of_scope",
  "confidential",
  "injection",
  "language",
];
const ATTACKS = ["injection", "confidential"];

const rank = (group: string) => {
  const i = GROUP_ORDER.indexOf(group);
  return i < 0 ? GROUP_ORDER.length : i;
};

export function summarize(run: Run) {
  const names = [...new Set(run.cases.map((c) => c.group))].sort((a, b) => rank(a) - rank(b));
  let n = 0;
  const groups = names.map((group) => {
    const cases = run.cases.filter((c) => c.group === group).map((c) => ({ ...c, n: n++ }));
    return { group, passed: cases.filter((c) => c.passed).length, cases };
  });
  return { total: run.cases.length, passed: run.cases.filter((c) => c.passed).length, groups };
}

export function showcase(run: Run, n: number): Case[] {
  return ATTACKS.flatMap((g) => run.cases.filter((c) => c.group === g && c.passed && c.reply)).slice(0, n);
}
