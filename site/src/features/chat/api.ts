// Chat API client: the browser calls (/api/chat POST and DELETE, /api/attachments, /api/lead), same origin, JSON or
// one file's raw bytes in, JSON or NDJSON (a streamed answer) out.
// Responsibility: turn every failure (network, non-JSON page, unknown status) into a status the page knows, so the
// visitor sees a fixed notice and the contact, never an error; and keep the session rules (conversation). Public API:
// conversation, sendMessage, uploadFile, submitLead, clearConversation and their result types. Used by:
// features/chat/chat.tsx. Tests: api.test.ts.

import type { Lang } from "@/lib/lang";

const CHAT = ["ok", "invalid", "rate_limited", "daily_limit", "busy", "conversation_limit", "resting", "offline", "blocked", "challenge"] as const;
const LEAD = ["ok", "invalid", "rate_limited", "unavailable"] as const;
const REFUSALS = ["type", "too_big", "unreadable", "no_text", "busy", "too_many", "rate_limited", "offline", "challenge"] as const;
export type ChatStatus = (typeof CHAT)[number];
export type ChatResult = { status: ChatStatus; reply: string; offerContact: boolean };
export type LeadStatus = (typeof LEAD)[number];
export type LeadResult = { status: LeadStatus; whatsapp?: string };
export type FileRefusal = (typeof REFUSALS)[number];
export type UploadResult = { status: "ok"; id: string; summary: string } | { status: "refused"; reason: FileRefusal };
export type LeadFields = { name: string; company: string; email: string; linkedin: string; kind: "hiring" | "project" };

const OFFLINE: ChatResult = { status: "offline", reply: "", offerContact: true };
const MAX_FILE = 10 * 1024 * 1024; // the API's limit; each type has a smaller one there

type Data = Record<string, unknown>;

const isOne = <T extends string>(list: readonly T[], value: unknown): value is T =>
  (list as readonly unknown[]).includes(value);

function post(url: string, body: unknown, signal?: AbortSignal, headers: Record<string, string> = {}): Promise<Response> {
  return fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify(body),
    signal,
  });
}

// An "ok" answer streams as NDJSON: {"type":"delta","text"} pieces, then one {"type":"done","status","offer_contact"}.
// Each piece goes to onDelta as it arrives. A stream that breaks or ends without "done" is offline, and anything but
// "ok" drops the text already shown (the output guard blocked it, or the worker dropped).
export async function sendMessage(
  message: string,
  pageLang: Lang,
  {
    files = [],
    onDelta = () => {},
    signal,
    human,
  }: { files?: string[]; onDelta?: (text: string) => void; signal?: AbortSignal; human?: string } = {},
): Promise<ChatResult> {
  try {
    // human: the browser proof (human.ts), sent only to open a conversation
    const body = { message, page_lang: pageLang, ...(files.length ? { attachments: files } : {}), ...(human ? { human } : {}) };
    const response = await post("/api/chat", body, signal);
    if (!response.headers.get("content-type")?.includes("ndjson")) return chatResult(await response.json());
    const lines = response.body!.pipeThrough(new TextDecoderStream()).getReader();
    let buffer = "";
    let reply = "";
    for (;;) {
      const { value, done } = await lines.read();
      if (done) return OFFLINE;
      const parts = (buffer + value).split("\n");
      buffer = parts.pop()!;
      for (const line of parts.filter((l) => l.trim())) {
        const event = JSON.parse(line) as Data;
        if (event.type === "done") return chatResult(event, reply);
        reply += String(event.text ?? "");
        onDelta(String(event.text ?? ""));
      }
    }
  } catch {
    return OFFLINE;
  }
}

// Only a streamed "ok" carries text; every other answer is a JSON status.
function chatResult(data: Data | null, streamed = ""): ChatResult {
  if (!data || !isOne(CHAT, data.status)) return OFFLINE;
  const status = data.status;
  return { status, reply: status === "ok" ? streamed : "", offerContact: data.offer_contact === true };
}

// One file as raw bytes; the API converts it and keeps the result for this conversation until the answer ends.
export async function uploadFile(file: Blob, human?: string): Promise<UploadResult> {
  if (file.size > MAX_FILE) return { status: "refused", reason: "too_big" };
  try {
    const response = await fetch("/api/attachments", {
      method: "POST",
      headers: { "Content-Type": "application/octet-stream", ...(human ? { "X-Human": human } : {}) },
      body: file,
    });
    const data = (await response.json()) as Data;
    if (data.status === "ok" && typeof data.id === "string") return { status: "ok", id: data.id, summary: String(data.summary ?? "") };
    const reason = String(data.status === "rejected" ? data.reason : data.status);
    return { status: "refused", reason: isOne(REFUSALS, reason) ? reason : "unreadable" };
  } catch (error) {
    return { status: "refused", reason: error instanceof SyntaxError ? "unreadable" : "offline" };
  }
}

// human: a fresh browser proof, which the WhatsApp number needs (conversation.lead sends one with every hiring lead)
export async function submitLead(fields: LeadFields, honeypot: string, pageLang: Lang, human?: string): Promise<LeadResult> {
  const data: Data | null = await post("/api/lead", { ...fields, website: honeypot, page_lang: pageLang }, undefined, human ? { "X-Human": human } : {})
    .then((r) => r.json())
    .catch(() => null);
  if (!data || !isOne(LEAD, data.status)) return { status: "unavailable" };
  return typeof data.whatsapp === "string" ? { status: "ok", whatsapp: data.whatsapp } : { status: data.status };
}

// The session rules in one place. The API keeps the conversation behind an HttpOnly cookie the page can't see, so this
// remembers whether one is open: a request without one carries the browser proof (`proof`, human.ts), and a
// "challenge" while one is open (the server forgot it after 2 h idle) is proved and sent once more. An "ok" opens it,
// a "challenge" closes it, and a message cleared while it ran changes nothing. Files upload side by side, except that
// without a session they go one at a time until one opens it (or each would start a session of its own).
export function conversation(proof: () => Promise<string | undefined>) {
  let open = false;
  const outcome = (r: ChatResult | UploadResult) => (r.status === "refused" ? r.reason : r.status);
  async function call<R extends ChatResult | UploadResult>(request: (human?: string) => Promise<R>, signal?: AbortSignal) {
    const ask = async (prove: boolean) => request(prove ? await proof() : undefined);
    let result = await ask(!open);
    if (outcome(result) === "challenge" && open) result = await ask(true);
    if (!signal?.aborted) open = outcome(result) === "ok" || (open && outcome(result) !== "challenge");
    return result;
  }
  return {
    send: (message: string, pageLang: Lang, options: { files?: string[]; onDelta?: (text: string) => void; signal: AbortSignal }) =>
      call((human) => sendMessage(message, pageLang, { ...options, human }), options.signal),
    async upload(files: Blob[], onDone: (index: number, result: UploadResult) => void) {
      const run = async (i: number) => onDone(i, await call((human) => uploadFile(files[i], human)));
      let i = 0;
      while (!open && i < files.length) await run(i++);
      await Promise.all(files.slice(i).map((_, j) => run(i + j)));
    },
    // a hiring lead gets the WhatsApp number only from a person: always with a fresh proof, since the conversation this
    // page thinks is open may have expired on the server (2 h idle); a project lead never needs one
    lead: async (fields: LeadFields, honeypot: string, pageLang: Lang) =>
      submitLead(fields, honeypot, pageLang, fields.kind === "hiring" ? await proof() : undefined),
    clear() {
      open = false; // the API forgets the session; the next request starts a new one
      return clearConversation();
    },
  };
}

export async function clearConversation(): Promise<void> {
  try {
    await fetch("/api/chat", { method: "DELETE" });
  } catch {
    // offline: the server forgets the conversation on its own within 2 hours
  }
}
