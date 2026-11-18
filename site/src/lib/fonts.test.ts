import { describe, expect, it, vi } from "vitest";
import { FONT_BOOT, FONT_WAIT_MS } from "./fonts";

// The boot script runs before paint, as a string: run that same string with a fake document and clock.
function boot(fonts: { ready: Promise<unknown> } | undefined) {
  const classes = new Set<string>();
  const classList = { add: (c: string) => classes.add(c), remove: (c: string) => classes.delete(c) };
  const document = { documentElement: { classList }, fonts };
  new Function("document", "setTimeout", FONT_BOOT)(document, setTimeout);
  return classes;
}

describe("FONT_BOOT", () => {
  it("holds the opening until the fonts are ready, then lets it play", async () => {
    let ready!: () => void;
    const classes = boot({ ready: new Promise<void>((r) => (ready = r)) });
    expect(classes.has("fonts-wait")).toBe(true);
    ready();
    await Promise.resolve();
    expect(classes.has("fonts-wait")).toBe(false);
  });

  it("lets it play after FONT_WAIT_MS when the fonts never come", () => {
    vi.useFakeTimers();
    try {
      const classes = boot({ ready: new Promise(() => {}) });
      vi.advanceTimersByTime(FONT_WAIT_MS - 1);
      expect(classes.has("fonts-wait")).toBe(true);
      vi.advanceTimersByTime(1);
      expect(classes.has("fonts-wait")).toBe(false);
    } finally {
      vi.useRealTimers();
    }
  });

  it("holds nothing in a browser without the font loading API", () => {
    expect(boot(undefined).has("fonts-wait")).toBe(false);
  });
});
