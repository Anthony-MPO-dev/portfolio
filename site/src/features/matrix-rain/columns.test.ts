import { describe, expect, it } from "vitest";
import { GLYPHS, rainColumns } from "./columns";

describe("rainColumns", () => {
  it("fits about one column every 30 px, never fewer than 10 nor more than 44", () => {
    expect(rainColumns(360, 800, Math.random)).toHaveLength(12);
    expect(rainColumns(100, 800, Math.random)).toHaveLength(10);
    expect(rainColumns(2560, 800, Math.random)).toHaveLength(44);
  });

  it("gives each column 14 to 27 glyphs, one per line, from the code-like set", () => {
    for (const random of [() => 0, () => 0.999]) {
      for (const column of rainColumns(600, 800, random)) {
        const glyphs = column.text.split("\n");
        expect(glyphs.length).toBeGreaterThanOrEqual(14);
        expect(glyphs.length).toBeLessThanOrEqual(27);
        expect(glyphs.every((g) => g.length === 1 && GLYPHS.includes(g))).toBe(true);
      }
    }
  });

  it("falls in 5 to 14 s, starts part-way through its fall, and falls past the bottom of the box", () => {
    const [slow] = rainColumns(600, 800, () => 0.999);
    const [fast] = rainColumns(600, 800, () => 0);
    expect(fast.duration).toBe(5);
    expect(slow.duration).toBeCloseTo(14, 1);
    expect(slow.delay).toBeLessThanOrEqual(0);
    expect(slow.delay).toBeGreaterThan(-slow.duration);
    expect(fast.fall).toBe(840);
  });
});
