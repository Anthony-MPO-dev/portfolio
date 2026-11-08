import { describe, expect, it } from "vitest";
import { figureAt, parseFigure } from "./count";

describe("parseFigure", () => {
  it("splits a figure into its number and the text around it", () => {
    expect(parseFigure("3x")).toEqual({ prefix: "", value: 3, decimals: 0, suffix: "x" });
    expect(parseFigure("13")).toEqual({ prefix: "", value: 13, decimals: 0, suffix: "" });
    expect(parseFigure("~100/day")).toEqual({ prefix: "~", value: 100, decimals: 0, suffix: "/day" });
  });

  it("keeps the decimals, so the count shows the same precision", () => {
    expect(parseFigure("0.0205")).toEqual({ prefix: "", value: 0.0205, decimals: 4, suffix: "" });
  });

  it("returns null when there is no number to count", () => {
    expect(parseFigure("fast")).toBeNull();
    expect(parseFigure("")).toBeNull();
  });
});

describe("figureAt", () => {
  const three = parseFigure("3x")!;

  it("starts at zero and ends exactly on the figure", () => {
    expect(figureAt(three, 0)).toBe("0x");
    expect(figureAt(three, 1)).toBe("3x");
    expect(figureAt(three, 1.5)).toBe("3x");
  });

  it("never shows the final figure, or more, before the end", () => {
    const thirteen = parseFigure("13")!;
    const shown = Array.from({ length: 100 }, (_, i) => Number(figureAt(thirteen, i / 100)));
    expect(Math.max(...shown)).toBeLessThan(13);
    expect(shown).toEqual([...shown].sort((a, b) => a - b)); // only goes up
  });

  it("rises fast and slows down at the end", () => {
    const hundred = parseFigure("100")!;
    expect(Number(figureAt(hundred, 0.5))).toBeGreaterThan(75);
  });

  it("formats with the figure's decimals and surrounding text", () => {
    expect(figureAt(parseFigure("0.0205")!, 1)).toBe("0.0205");
    expect(figureAt(parseFigure("~100/day")!, 0)).toBe("~0/day");
  });
});
