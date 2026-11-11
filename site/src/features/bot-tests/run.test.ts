import { describe, expect, it } from "vitest";
import { type Run, showcase, summarize } from "./run";

const c = (id: string, group: string, passed: boolean, reply: string | null = passed ? `reply ${id}` : null) => ({
  id,
  group,
  q: `question ${id}`,
  passed,
  seconds: 2,
  reply,
});

const run: Run = {
  date: "2026-11-11",
  model: "haiku",
  cases: [
    c("f1", "facts", true),
    c("i1", "injection", true),
    c("f2", "facts", false),
    c("x1", "brand_new_group", true),
    c("k1", "confidential", true),
    c("i2", "injection", true),
    c("i3", "injection", false),
  ],
};

describe("summarize", () => {
  it("counts every case and every pass", () => {
    const s = summarize(run);
    expect([s.total, s.passed]).toEqual([7, 5]);
  });

  it("groups the cases in the page's order, unknown groups last, keeping each group's run order", () => {
    const s = summarize(run);
    expect(s.groups.map((g) => g.group)).toEqual(["facts", "confidential", "injection", "brand_new_group"]);
    expect(s.groups[2].cases.map((x) => x.id)).toEqual(["i1", "i2", "i3"]);
  });

  it("numbers the cases across the whole run, so the squares light up one after another", () => {
    const s = summarize(run);
    expect(s.groups.flatMap((g) => g.cases.map((x) => x.n))).toEqual([0, 1, 2, 3, 4, 5, 6]);
  });

  it("counts the passes of each group", () => {
    expect(summarize(run).groups.map((g) => g.passed)).toEqual([1, 1, 2, 1]);
  });
});

describe("showcase", () => {
  it("picks passing attacks with a reply, injection first, then confidential", () => {
    expect(showcase(run, 3).map((x) => x.id)).toEqual(["i1", "i2", "k1"]);
  });

  it("never shows a failed case or a case without a reply", () => {
    const only = showcase(
      { ...run, cases: [c("i9", "injection", false, "leak"), c("i8", "injection", true, null)] },
      3,
    );
    expect(only).toEqual([]);
  });

  it("stops at the number asked for", () => {
    expect(showcase(run, 1)).toHaveLength(1);
  });
});
