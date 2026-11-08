// Chat API client: the three browser calls (/api/chat POST and DELETE, /api/lead), same origin, JSON in, JSON or NDJSON (a streamed answer) out.
// Responsibility: turn every failure (network, non-JSON page, unknown status) into a status the page knows, so the
// visitor sees a fixed notice and the contact, never an error. Public API: sendMessage, submitLead,
// clearConversation and their result types. Used by: features/chat/chat.tsx. Tests: api.test.ts.

export type Lang = "en" | "pt";
export type ChatStatus = "ok" | "invalid" | "rate_limited" | "busy" | "conversation_limit" | "offline" | "blocked";
export type ChatResult = { status: ChatStatus; reply: string; offerContact: boolean };
export type LeadStatus = "ok" | "invalid" | "rate_limited" | "unavailable";
export type LeadResult = { status: LeadStatus; whatsapp?: string };
export type LeadFields = { name: string; company: string; email: string; linkedin: string; kind: "hiring" | "project" };

const CHAT: readonly string[] = ["ok", "invalid", "rate_limited", "busy", "conversation_limit", "offline", "blocked"];
const LEAD: readonly string[] = ["ok", "invalid", "rate_limited", "unavailable"];
const OFFLINE: ChatResult = { status: "offline", reply: "", offerContact: true };

type Data = Record<string, unknown>;

function post(url: string, body: unknown, signal?: AbortSignal): Promise<Response> {
  return fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    credentials: "same-origin",
    signal,
  });
}

// An "ok" answer streams as NDJSON: {"type":"delta","text"} pieces, then one {"type":"done","status","offer_contact"}.
// Each piece goes to onDelta as it arrives. A stream that breaks or ends without "done" is offline, and anything but
// "ok" drops the text already shown (the output guard blocked it, or the worker dropped).
export async function sendMessage(
  message: string,
  pageLang: Lang,
  onDelta: (text: string) => void = () => {},
  signal?: AbortSignal,
): Promise<ChatResult> {
  try {
    const response = await post("/api/chat", { message, page_lang: pageLang }, signal);
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

function chatResult(data: Data | null, streamed?: string): ChatResult {
  if (!data || !CHAT.includes(data.status as string)) return OFFLINE;
  const status = data.status as ChatStatus;
  const reply = streamed === undefined ? String(data.reply ?? "") : status === "ok" ? streamed : "";
  return { status, reply, offerContact: data.offer_contact === true };
}

export async function submitLead(fields: LeadFields, honeypot: string, pageLang: Lang): Promise<LeadResult> {
  const data: Data | null = await post("/api/lead", { ...fields, website: honeypot, page_lang: pageLang })
    .then((r) => r.json())
    .catch(() => null);
  if (!data || !LEAD.includes(data.status as string)) return { status: "unavailable" };
  return typeof data.whatsapp === "string" ? { status: "ok", whatsapp: data.whatsapp } : { status: data.status as LeadStatus };
}

export async function clearConversation(): Promise<void> {
  try {
    await fetch("/api/chat", { method: "DELETE", credentials: "same-origin" });
  } catch {
    // offline: the server forgets the conversation on its own within 2 hours
  }
}
