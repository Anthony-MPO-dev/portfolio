import { afterEach, describe, expect, it, vi } from "vitest";
import { clearConversation, sendMessage, submitLead, uploadFile } from "./api";

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

  it("sends the browser proof only when given one", async () => {
    const fetch = respond(200, { status: "ok", reply: "Yes.", offer_contact: false });
    await sendMessage("Hi", "en", { human: "t-1" });
    await sendMessage("Hi", "en");
    const bodies = fetch.mock.calls.map((c) => JSON.parse((c as unknown as [string, RequestInit])[1].body as string));
    expect(bodies.map((b) => b.human)).toEqual(["t-1", undefined]);
  });

  it("reads a refused browser proof", async () => {
    respond(200, { status: "challenge", reply: "", offer_contact: false });
    expect((await sendMessage("q", "en")).status).toBe("challenge");
  });

  it("reads a reply the output guard blocked", async () => {
    respond(200, { status: "blocked", reply: null, offer_contact: true });
    expect(await sendMessage("q", "en")).toEqual({ status: "blocked", reply: "", offerContact: true });
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

describe("sendMessage, streamed", () => {
  function streamed(...chunks: string[]) {
    const bytes = new TextEncoder();
    const body = new ReadableStream({
      start(c) {
        chunks.forEach((chunk) => c.enqueue(bytes.encode(chunk)));
        c.close();
      },
    });
    const headers = { "content-type": "application/x-ndjson" };
    vi.stubGlobal("fetch", vi.fn(async () => new Response(body, { status: 200, headers })));
  }
  const delta = (text: string) => JSON.stringify({ type: "delta", text }) + "\n";
  const done = (status: string, offer = false) => JSON.stringify({ type: "done", status, offer_contact: offer }) + "\n";

  it("hands each piece over as it arrives and returns the whole reply", async () => {
    streamed(delta("He is "), delta("open.") + done("ok", true));
    const pieces: string[] = [];
    expect(await sendMessage("q", "en", { onDelta: (t) => pieces.push(t) })).toEqual({ status: "ok", reply: "He is open.", offerContact: true });
    expect(pieces).toEqual(["He is ", "open."]);
  });

  it("joins a line split across chunks", async () => {
    const line = delta("Brazil, UTC-3.");
    streamed(line.slice(0, 9), line.slice(9), done("ok"));
    expect((await sendMessage("q", "en")).reply).toBe("Brazil, UTC-3.");
  });

  it("drops what was shown when the output guard blocks the reply", async () => {
    streamed(delta("Sure, "), done("blocked", true));
    expect(await sendMessage("q", "en")).toEqual({ status: "blocked", reply: "", offerContact: true });
  });

  it.each([
    ["the stream stops before the end", [delta("Half ")]],
    ["a line isn't JSON", ["oops\n"]],
  ])("is offline when %s", async (_, chunks) => {
    streamed(...chunks);
    expect(await sendMessage("q", "en")).toEqual({ status: "offline", reply: "", offerContact: true });
  });
});

describe("files", () => {
  it("sends the browser proof in a header when given one", async () => {
    const fetch = respond(200, { status: "ok", id: "f1", summary: "pdf, 1 page" });
    await uploadFile(new Blob(["x"]), "t-2");
    const [, init] = fetch.mock.calls[0] as unknown as [string, RequestInit];
    expect(new Headers(init.headers).get("x-human")).toBe("t-2");
  });

  it("names the uploaded files in the message", async () => {
    const fetch = respond(200, { status: "ok", reply: "Read.", offer_contact: false });
    await sendMessage("What is this?", "en", { files: ["ab12", "cd34"] });
    const [, init] = fetch.mock.calls[0] as unknown as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({ message: "What is this?", page_lang: "en", attachments: ["ab12", "cd34"] });
  });

  it("uploads one file as raw bytes and reads its id and summary", async () => {
    const fetch = respond(200, { status: "ok", id: "ab12", summary: "pdf, 3 pages" });
    expect(await uploadFile(new Blob(["%PDF"]))).toEqual({ status: "ok", id: "ab12", summary: "pdf, 3 pages" });
    const [url, init] = fetch.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/attachments");
    expect(new Headers(init.headers).get("content-type")).toBe("application/octet-stream");
  });

  it.each([
    [422, { status: "rejected", reason: "no_text" }, "no_text"],
    [429, { status: "too_many" }, "too_many"],
    [422, { status: "rejected", reason: "weird" }, "unreadable"],
    [502, "bad gateway", "unreadable"],
  ])("says why a file was refused (%s)", async (code, body, reason) => {
    respond(code, body);
    expect(await uploadFile(new Blob(["x"]))).toEqual({ status: "refused", reason });
  });

  it("refuses a file over 10 MB without sending it, and is offline when the network fails", async () => {
    const fetch = respond(200, {});
    expect(await uploadFile(new Blob([new Uint8Array(10 * 1024 * 1024 + 1)]))).toEqual({ status: "refused", reason: "too_big" });
    expect(fetch).not.toHaveBeenCalled();
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("down"))));
    expect(await uploadFile(new Blob(["x"]))).toEqual({ status: "refused", reason: "offline" });
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
