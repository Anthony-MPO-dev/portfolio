import { describe, expect, it } from "vitest";
import { FULL_TIME_HOURS, WORK_WEEKS, clampInput, fullTimePeople, hoursBack, monthlyHours, parseRate } from "./hours";

describe("hoursBack", () => {
  it("multiplies people, weekly hours and the cut over the working year", () => {
    expect(WORK_WEEKS).toBe(46);
    expect(hoursBack({ people: 5, hoursPerWeek: 8, cutPercent: 50 })).toBe(920);
  });

  it("rounds to whole hours", () => {
    expect(hoursBack({ people: 1, hoursPerWeek: 1, cutPercent: 15 })).toBe(7); // 6.9
  });

  it("gives zero, never a negative or NaN, for bad numbers", () => {
    expect(hoursBack({ people: 0, hoursPerWeek: 8, cutPercent: 50 })).toBe(0);
    expect(hoursBack({ people: -3, hoursPerWeek: 8, cutPercent: 50 })).toBe(0);
    expect(hoursBack({ people: Number.NaN, hoursPerWeek: 8, cutPercent: 50 })).toBe(0);
  });

  it("never cuts more than all of the time", () => {
    expect(hoursBack({ people: 1, hoursPerWeek: 10, cutPercent: 140 })).toBe(460);
  });
});

describe("fullTimePeople", () => {
  it("counts a full-time person as 40 hours a week over the working year", () => {
    expect(FULL_TIME_HOURS).toBe(40 * 46);
    expect(fullTimePeople(1840)).toBe(1);
    expect(fullTimePeople(920)).toBe(0.5);
  });

  it("keeps one decimal", () => {
    expect(fullTimePeople(1000)).toBe(0.5); // 0.543
    expect(fullTimePeople(3000)).toBe(1.6); // 1.630
  });
});

describe("monthlyHours", () => {
  it("piles the year's hours up month by month, ending on the total", () => {
    const months = monthlyHours(1200);
    expect(months).toHaveLength(12);
    expect(months[0]).toBe(100);
    expect(months[11]).toBe(1200);
  });

  it("rounds each month and still ends exactly on the total", () => {
    const months = monthlyHours(7);
    expect(months[11]).toBe(7);
    expect(months.every((m, i) => i === 0 || m >= months[i - 1])).toBe(true);
  });
});

describe("parseRate", () => {
  it("reads a plain number in any currency's habits: dot or comma for decimals", () => {
    expect(parseRate("50")).toBe(50);
    expect(parseRate("42.5")).toBe(42.5);
    expect(parseRate("42,5")).toBe(42.5);
    expect(parseRate(" 60 ")).toBe(60);
  });

  it("gives null for empty, zero, negative or non-numbers, so nothing is shown", () => {
    expect(parseRate("")).toBeNull();
    expect(parseRate("0")).toBeNull();
    expect(parseRate("-5")).toBeNull();
    expect(parseRate("abc")).toBeNull();
    expect(parseRate("1.2.3")).toBeNull();
  });
});

describe("clampInput", () => {
  it("keeps a whole number inside the field's range", () => {
    expect(clampInput("12", 1, 40)).toBe(12);
    expect(clampInput("7.6", 1, 40)).toBe(8);
    expect(clampInput("99", 1, 40)).toBe(40);
    expect(clampInput("0", 1, 40)).toBe(1);
  });

  it("falls back to the minimum when the field is empty or not a number", () => {
    expect(clampInput("", 1, 40)).toBe(1);
    expect(clampInput("x", 1, 40)).toBe(1);
  });
});
