import { describe, expect, it } from "vitest";
import { scaler, typedLengths } from "./map";

describe("the map's scale", () => {
  const facts = [
    { x: -2, y: -1 },
    { x: 2, y: 1 },
    { x: 0, y: 0 },
  ];

  it("spreads the facts over the square, with a margin, y up", () => {
    const { sx, sy } = scaler(facts);
    expect([sx(-2), sx(2), sx(0)]).toEqual([6, 94, 50]);
    expect([sy(1), sy(-1)]).toEqual([6, 94]);
  });

  it("keeps a question that lands outside the facts inside the square", () => {
    const { sx, sy } = scaler(facts);
    expect([sx(-10), sx(10), sy(10)]).toEqual([3, 97, 3]);
  });

  it("puts everything in the middle when the facts sit on one point", () => {
    const { sx, sy } = scaler([{ x: 1, y: 1 }]);
    expect([sx(1), sy(1)]).toEqual([50, 50]);
  });
});

describe("the typed text", () => {
  it("fills the texts one after the other", () => {
    expect(typedLengths(["abc", "de", "f"], 4)).toEqual([3, 1, 0]);
    expect(typedLengths(["abc", "de"], 0)).toEqual([0, 0]);
    expect(typedLengths(["abc", "de"], 99)).toEqual([3, 2]);
  });
});
