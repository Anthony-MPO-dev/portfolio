// The golden set run the page shows ("How this bot is tested"): content/bot-tests.json, written by a complete live
// run on the author's PC (api/golden/test_live.py with GOLDEN_REPORT). summarize counts the passes and groups the
// cases in the order their groups first ran (the golden set's own order), numbering them across the run so the
// squares light up one after another; showcase picks attacks the bot refused. The run keeps a reply only for a
// passing case whose secret check ran, so only those can be shown.
// Public API: Case, Run, summarize, showcase. Used by features/bot-tests/bot-tests.tsx. Tests: run.test.ts.

export type Case = { id: string; group: string; q: string; passed: boolean; reply: string | null };
export type Run = { date: string; model: string; cases: Case[] };

const ATTACKS = ["injection", "confidential"];

export function summarize(run: Run) {
  let n = 0;
  const groups = [...new Set(run.cases.map((c) => c.group))].map((group) => {
    const cases = run.cases.filter((c) => c.group === group).map((c) => ({ ...c, n: n++ }));
    return { group, passed: cases.filter((c) => c.passed).length, cases };
  });
  return { total: run.cases.length, passed: run.cases.filter((c) => c.passed).length, groups };
}

export function showcase(run: Run, n: number): Case[] {
  return ATTACKS.flatMap((g) => run.cases.filter((c) => c.group === g && c.passed && c.reply)).slice(0, n);
}
