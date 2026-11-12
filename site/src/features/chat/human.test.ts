import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { proofWith, type Turnstile } from "./human";

const box = {} as HTMLElement;

function fakeTurnstile() {
  const widget: { options?: Record<string, (...a: unknown[]) => void> } = {};
  const api: Turnstile & { removed: string[] } = {
    removed: [],
    render: (_box, options) => {
      widget.options = options as Record<string, (...a: unknown[]) => void>;
      return "w1";
    },
    remove: (id) => api.removed.push(id),
  };
  return { api, widget };
}

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe("the browser proof", () => {
  it("gives Cloudflare's token and removes the widget", async () => {
    const { api, widget } = fakeTurnstile();
    const token = proofWith({ sitekey: "k", load: async () => api })(box);
    await vi.waitFor(() => expect(widget.options).toBeDefined());
    expect(widget.options!.sitekey).toBe("k");
    expect(widget.options!.appearance).toBe("interaction-only"); // seen only when Cloudflare wants a click
    widget.options!.callback("t-123");
    expect(await token).toBe("t-123");
    expect(api.removed).toEqual(["w1"]);
  });

  it("gives nothing without a site key, without loading Cloudflare's script", async () => {
    const load = vi.fn();
    expect(await proofWith({ sitekey: undefined, load })(box)).toBeUndefined();
    expect(load).not.toHaveBeenCalled();
  });

  it.each([
    ["the script fails to load", async () => Promise.reject(new Error("blocked"))],
    [
      "render throws",
      async () => ({
        render: () => {
          throw new Error("bad");
        },
        remove: () => {},
      }),
    ],
  ])("gives nothing, never an error, when %s", async (_, load) => {
    expect(await proofWith({ sitekey: "k", load })(box)).toBeUndefined();
  });

  it("gives nothing on Cloudflare's error callback", async () => {
    const { api, widget } = fakeTurnstile();
    const token = proofWith({ sitekey: "k", load: async () => api })(box);
    await vi.waitFor(() => expect(widget.options).toBeDefined());
    widget.options!["error-callback"]();
    expect(await token).toBeUndefined();
  });

  it("gives up after the wait, script load included, so the chat never hangs", async () => {
    const token = proofWith({ sitekey: "k", load: () => new Promise<Turnstile>(() => {}), wait: 15_000 })(box);
    await vi.advanceTimersByTimeAsync(15_000);
    expect(await token).toBeUndefined();
  });

  it("waits longer once the visitor is asked to click", async () => {
    const { api, widget } = fakeTurnstile();
    const token = proofWith({ sitekey: "k", load: async () => api, wait: 15_000, waitForClick: 60_000 })(box);
    await vi.waitFor(() => expect(widget.options).toBeDefined());
    widget.options!["before-interactive-callback"]();
    await vi.advanceTimersByTimeAsync(30_000);
    widget.options!.callback("clicked");
    expect(await token).toBe("clicked");
  });
});
