import { afterEach, describe, expect, it, vi } from "vitest";
import { clearConversation, sendMessage, submitLead } from "./api";

function respond(status: number, body: unknown) {
  const fetch = vi.fn(async () => new Response(status === 204 ? null : typeof body === "string" ? body : JSON.stringify(body), { status }));
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

afterEach(() => vi.unstubAllGlobals());

describe("sendMessage", () => {
  it("posts the message and the page language as JSON and reads the answer", async () => {
    const fetch = respond(200, { status: "ok", reply: "Yes.", offer_contact: true });
    expect(await sendMessage("Open to remote?", "pt")).toEqual({ status: "ok", reply: "Yes.", offerContact: true });
    const [url, init] = fetch.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/chat");
    expect(init.method).toBe("POST");
    expect(new Headers(init.headers).get("content-type")).toBe("application/json");
    expect(JSON.parse(init.body as string)).toEqual({ message: "Open to remote?", page_lang: "pt" });
  });

  it("reads a limit from a 429", async () => {
    respond(429, { status: "rate_limited", reply: "", offer_contact: false });
    expect((await sendMessage("q", "en")).status).toBe("rate_limited");
  });

  it.each([
    ["the network fails", () => vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("down"))))],
    ["the answer isn't JSON", () => respond(404, "<html>not found</html>")],
    ["the status is unknown", () => respond(200, { status: "weird", reply: "x" })],
  ])("is offline, with the contact offered, when %s", async (_, setup) => {
    setup();
    expect(await sendMessage("q", "en")).toEqual({ status: "offline", reply: "", offerContact: true });
  });
});

describe("submitLead", () => {
  const fields = { name: "Ana", company: "Acme", email: "ana@acme.test", linkedin: "", kind: "hiring" as const };

  it("posts the fields, the honeypot and the page language, and passes the WhatsApp number on", async () => {
    const fetch = respond(200, { status: "ok", whatsapp: "+15550100" });
    expect(await submitLead(fields, "", "en")).toEqual({ status: "ok", whatsapp: "+15550100" });
    const [url, init] = fetch.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/lead");
    expect(JSON.parse(init.body as string)).toEqual({ ...fields, website: "", page_lang: "en" });
  });

  it("is unavailable when the request fails or the answer is unknown", async () => {
    respond(502, "bad gateway");
    expect(await submitLead(fields, "", "en")).toEqual({ status: "unavailable" });
    respond(200, { status: "weird" });
    expect(await submitLead(fields, "", "en")).toEqual({ status: "unavailable" });
  });
});

it("clearConversation sends a DELETE and never throws", async () => {
  const fetch = respond(204, "");
  await clearConversation();
  expect((fetch.mock.calls[0] as unknown as [string, RequestInit])[1].method).toBe("DELETE");
  vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("down"))));
  await expect(clearConversation()).resolves.toBeUndefined();
});
