import { afterEach, describe, expect, it, vi } from "vitest";
import { clearConversation, conversation, sendMessage, submitLead, uploadFile } from "./api";

function respond(status: number, body: unknown) {
  const fetch = vi.fn(async () => new Response(status === 204 ? null : typeof body === "string" ? body : JSON.stringify(body), { status }));
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

afterEach(() => vi.unstubAllGlobals());

describe("sendMessage", () => {
  it("posts the message and the page language as JSON", async () => {
    const fetch = respond(429, { status: "rate_limited" });
    await sendMessage("Open to remote?", "pt");
    const [url, init] = fetch.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/chat");
    expect(init.method).toBe("POST");
    expect(new Headers(init.headers).get("content-type")).toBe("application/json");
    expect(JSON.parse(init.body as string)).toEqual({ message: "Open to remote?", page_lang: "pt" });
  });

  it("sends the browser proof only when given one", async () => {
    const fetch = respond(200, { status: "ok", offer_contact: false });
    await sendMessage("Hi", "en", { human: "t-1" });
    await sendMessage("Hi", "en");
    const bodies = fetch.mock.calls.map((c) => JSON.parse((c as unknown as [string, RequestInit])[1].body as string));
    expect(bodies.map((b) => b.human)).toEqual(["t-1", undefined]);
  });

  it("reads a refused browser proof", async () => {
    respond(200, { status: "challenge", offer_contact: false });
    expect((await sendMessage("q", "en")).status).toBe("challenge");
  });

  it("reads a reply the output guard blocked", async () => {
    respond(200, { status: "blocked", offer_contact: true });
    expect(await sendMessage("q", "en")).toEqual({ status: "blocked", reply: "", offerContact: true });
  });

  it("reads a limit from a 429", async () => {
    respond(429, { status: "rate_limited", offer_contact: false });
    expect((await sendMessage("q", "en")).status).toBe("rate_limited");
  });

  it.each([
    ["the network fails", () => vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("down"))))],
    ["the answer isn't JSON", () => respond(404, "<html>not found</html>")],
    ["the status is unknown", () => respond(200, { status: "weird" })],
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
    const fetch = respond(200, { status: "ok", offer_contact: false });
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

describe("conversation (the session rules)", () => {
  // Each POST answers the next status in line (a chat "done" line, or an upload's JSON); the log shows which overlap.
  function answers(...statuses: string[]) {
    const log: string[] = [];
    const proofs: (string | null)[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init: RequestInit) => {
        if (init.method === "DELETE") return new Response(null, { status: 204 });
        const upload = url === "/api/attachments";
        proofs.push(upload ? new Headers(init.headers).get("x-human") : (JSON.parse(init.body as string).human ?? null));
        log.push("start");
        await Promise.resolve();
        log.push("end");
        const status = statuses.shift();
        if (upload) return new Response(JSON.stringify({ status, id: "f" }));
        return new Response(JSON.stringify({ type: "done", status }) + "\n", { headers: { "content-type": "application/x-ndjson" } });
      }),
    );
    return { log, proofs };
  }
  const open = () => ({ signal: new AbortController().signal });

  it("proves the browser on the first message only", async () => {
    const { proofs } = answers("ok", "ok");
    const talk = conversation(async () => "t");
    await talk.send("a", "en", open());
    await talk.send("b", "en", open());
    expect(proofs).toEqual(["t", null]);
  });

  it("proves it once more when the server forgot the session, but not after its proof was refused", async () => {
    const { proofs } = answers("ok", "challenge", "ok", "challenge");
    const talk = conversation(async () => "t");
    await talk.send("a", "en", open());
    expect((await talk.send("b", "en", open())).status).toBe("ok");
    await talk.clear();
    expect((await talk.send("c", "en", open())).status).toBe("challenge");
    expect(proofs).toEqual(["t", null, "t", "t"]);
  });

  it("uploads the first file alone while there is no session, then the rest side by side", async () => {
    const { log, proofs } = answers("ok", "ok", "ok");
    const done: number[] = [];
    await conversation(async () => "t").upload([new Blob(["1"]), new Blob(["2"]), new Blob(["3"])], (i) => done.push(i));
    expect(log).toEqual(["start", "end", "start", "start", "end", "end"]);
    expect(proofs).toEqual(["t", null, null]);
    expect(done.sort()).toEqual([0, 1, 2]);
  });

  it("sends a fresh proof with a hiring lead while no conversation is open, never with a project lead", async () => {
    const proofs: (string | null)[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init: RequestInit) => {
        if (url === "/api/lead") {
          proofs.push(new Headers(init.headers).get("x-human"));
          return new Response(JSON.stringify({ status: "ok" }));
        }
        return new Response(JSON.stringify({ type: "done", status: "ok" }) + "\n", { headers: { "content-type": "application/x-ndjson" } });
      }),
    );
    const jane = { name: "Jane", company: "Acme", email: "jane@acme.com", linkedin: "" };
    const talk = conversation(async () => "t");
    await talk.lead({ ...jane, kind: "hiring" }, "", "en");
    await talk.lead({ ...jane, kind: "project" }, "", "en");
    await talk.send("a", "en", open()); // a conversation opens: its cookie is enough from now on
    await talk.lead({ ...jane, kind: "hiring" }, "", "en");
    expect(proofs).toEqual(["t", null, null]);
  });

  it("leaves the session closed when a request cleared while it ran comes back ok", async () => {
    const { proofs } = answers("ok", "ok", "ok");
    const talk = conversation(async () => "t");
    await talk.send("a", "en", open());
    const clearing = new AbortController();
    const late = talk.send("b", "en", { signal: clearing.signal });
    clearing.abort();
    await talk.clear();
    expect((await late).status).toBe("ok"); // its answer was already in
    await talk.send("c", "en", open());
    expect(proofs).toEqual(["t", null, "t"]);
  });
});

it("clearConversation sends a DELETE and never throws", async () => {
  const fetch = respond(204, "");
  await clearConversation();
  expect((fetch.mock.calls[0] as unknown as [string, RequestInit])[1].method).toBe("DELETE");
  vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("down"))));
  await expect(clearConversation()).resolves.toBeUndefined();
});
