import { describe, expect, it } from "vitest";
import { copy, LANGS } from "./copy";

describe("the search's texts", () => {
  it("have the same keys and four sample questions in every language", () => {
    const keys = Object.keys(copy.en).sort();
    for (const { id } of LANGS) {
      expect(Object.keys(copy[id]).sort()).toEqual(keys);
      expect(copy[id].chips).toHaveLength(4);
    }
  });

  it("use simple punctuation: no em dash and no curly quotes", () => {
    const all = JSON.stringify(copy) + LANGS.map((l) => Object.values(copy[l.id]).map((v) => (typeof v === "function" ? v(5 as never) : v)).join(" ")).join(" ");
    expect(all).not.toMatch(/[—“”…]/);
  });
});
