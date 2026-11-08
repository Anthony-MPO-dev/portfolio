import { describe, expect, it } from "vitest";
import { scramble } from "./scramble";

const zero = () => 0;

describe("scramble", () => {
  it("returns the real text once the decode is done", () => {
    expect(scramble("The search fix", 1, zero)).toBe("The search fix");
  });

  it("swaps digits for digits and letters for capitals, keeping spaces and punctuation", () => {
    expect(scramble("Ab 12, x!", 0, zero)).toBe("AA 00, A!");
  });

  it("settles left to right: the share already decoded is the real text", () => {
    expect(scramble("abcd", 0.5, zero)).toBe("abAA");
  });

  it("draws the random characters from the random source", () => {
    expect(scramble("a1", 0, () => 0.99)).toBe("Z9");
  });
});
