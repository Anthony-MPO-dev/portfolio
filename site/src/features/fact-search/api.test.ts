import { afterEach, describe, expect, it, vi } from "vitest";
import { getFacts, searchFacts } from "./api";

function respond(status: number, body: unknown) {
  const fetch = vi.fn(async () => new Response(JSON.stringify(body), { status }));
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

afterEach(() => vi.unstubAllGlobals());

describe("getFacts", () => {
  it("reads the map of facts", async () => {
    respond(200, { facts: [{ id: 0, section: "At a glance", text: "Name: Anthony Muniz.", x: 0.1, y: -0.2 }] });
    expect(await getFacts()).toEqual([{ id: 0, section: "At a glance", text: "Name: Anthony Muniz.", x: 0.1, y: -0.2 }]);
  });

  it("gives null when the search is off or the network fails", async () => {
    respond(503, { status: "unavailable" });
    expect(await getFacts()).toBeNull();
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("offline"))));
    expect(await getFacts()).toBeNull();
  });
});

describe("searchFacts", () => {
  it("posts the question as JSON and reads the hits and the question's place", async () => {
    const fetch = respond(200, { status: "ok", hits: [{ id: 3, score: 0.84 }], x: 0.5, y: 0.25 });
    expect(await searchFacts("Does Kai use ChromaDB?")).toEqual({ status: "ok", hits: [{ id: 3, score: 0.84 }], x: 0.5, y: 0.25 });
    const [url, init] = fetch.mock.calls[0] as unknown as [string, RequestInit];
    expect([url, init.method, new Headers(init.headers).get("content-type")]).toEqual(["/api/search", "POST", "application/json"]);
    expect(JSON.parse(init.body as string)).toEqual({ q: "Does Kai use ChromaDB?" });
  });

  it.each([
    [429, "rate_limited"],
    [400, "invalid"],
    [503, "unavailable"],
  ] as const)("reads a %i as %s", async (code, status) => {
    respond(code, { status });
    expect((await searchFacts("q")).status).toBe(status);
  });

  it("is offline when the network fails or the answer is odd", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("offline"))));
    expect((await searchFacts("q")).status).toBe("offline");
    respond(200, { status: "weird" });
    expect((await searchFacts("q")).status).toBe("offline");
  });
});
