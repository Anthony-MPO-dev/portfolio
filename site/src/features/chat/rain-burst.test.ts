import { afterEach, describe, expect, it, vi } from "vitest";
import { rainBurst } from "./rain-burst";

afterEach(() => vi.unstubAllGlobals());

describe("rainBurst", () => {
  it("does nothing with reduced motion: no layer, not even a look at the page", () => {
    vi.stubGlobal("matchMedia", () => ({ matches: true }));
    vi.stubGlobal("document", undefined); // the test runs without a DOM: touching it would throw
    expect(() => rainBurst()).not.toThrow();
  });
});
