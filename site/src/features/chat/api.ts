// Chat API client: the three browser calls (/api/chat POST and DELETE, /api/lead), same origin, JSON only.
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

async function post(url: string, body: unknown): Promise<Record<string, unknown> | null> {
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      credentials: "same-origin",
    });
    return await response.json();
  } catch {
    return null;
  }
}

export async function sendMessage(message: string, pageLang: Lang): Promise<ChatResult> {
  const data = await post("/api/chat", { message, page_lang: pageLang });
  if (!data || !CHAT.includes(data.status as string)) return OFFLINE;
  return { status: data.status as ChatStatus, reply: String(data.reply ?? ""), offerContact: data.offer_contact === true };
}

export async function submitLead(fields: LeadFields, honeypot: string, pageLang: Lang): Promise<LeadResult> {
  const data = await post("/api/lead", { ...fields, website: honeypot, page_lang: pageLang });
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
