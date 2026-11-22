// Conversation state of the chat panel, as a pure reducer: what the visitor sent, the answers, the fixed notices
// (offline, limits) and where the contact form stands. Notice text lives in copy.ts; this module only names them.
// Public API: initial, reduce, and the State, Entry, Contact, Resume types. Used by: features/chat/chat.tsx,
// resume-panel.tsx.
// Tests: state.test.ts.
import type { ChatResult, ChatStatus, FileRefusal, LeadResult, ResumeResult, ResumeStatus, UploadResult } from "./api";

export type Notice = Exclude<ChatStatus, "ok">;
export type Entry =
  | { id: number; from: "you" | "bot"; text: string; files?: string[] }
  | { id: number; from: "notice"; notice: Notice };
// A file picked for the next message: uploading, ready (the API's id and summary) or refused (the reason).
export type FileChip =
  | { key: number; name: string; state: "uploading" }
  | { key: number; name: string; state: "ready"; id: string; summary: string }
  | { key: number; name: string; state: "refused"; reason: FileRefusal };
export type Contact =
  | { step: "none" | "offered" | "email" }
  | { step: "form"; error: boolean }
  | { step: "sent"; whatsapp?: string };
// partial: the answer as it streams in; it becomes an entry only when the answer ends "ok". contactAt: the entry that
// offered the contact; the form shows right after it, so messages sent later land below it, in view.
// resume: the resume panel, under the answer that offered it (token null: the standard pair; note: why the last
// tailoring ended as it did).
export type Resume = { at: number; token: string | null; company: string; role: string; note: ResumeStatus | null };
export type State = {
  entries: Entry[];
  pending: boolean;
  partial: string;
  files: FileChip[];
  contact: Contact;
  contactAt: number | null;
  resume: Resume | null;
};
export type Action =
  | { type: "send"; text: string }
  | { type: "delta"; text: string }
  | { type: "fileStart"; key: number; name: string }
  | { type: "fileDone"; key: number; result: UploadResult }
  | { type: "fileRemove"; key: number }
  | { type: "answer"; result: ChatResult }
  | { type: "openForm" }
  | { type: "leadDone"; result: LeadResult }
  | { type: "resumeDone"; result: ResumeResult }
  | { type: "clear" };

export const initial: State = { entries: [], pending: false, partial: "", files: [], contact: { step: "none" }, contactAt: null, resume: null };
const OFFER_ON: readonly Notice[] = [
  "offline",
  "resting",
  "rate_limited",
  "daily_limit",
  "conversation_limit",
  "blocked",
  "challenge",
];

export function reduce(state: State, action: Action): State {
  const id = state.entries.length;
  switch (action.type) {
    case "send": {
      const text = action.text.trim();
      if (!text || state.pending || state.files.some((f) => f.state === "uploading")) return state;
      const files = state.files.flatMap((f) => (f.state === "ready" ? [f.name] : []));
      const entry: Entry = files.length ? { id, from: "you", text, files } : { id, from: "you", text };
      return { ...state, pending: true, files: [], entries: [...state.entries, entry] };
    }
    case "fileStart":
      return { ...state, files: [...state.files, { key: action.key, name: action.name, state: "uploading" }] };
    case "fileDone": {
      const r = action.result;
      const done = (f: FileChip): FileChip =>
        r.status === "ok"
          ? { key: f.key, name: f.name, state: "ready", id: r.id, summary: r.summary }
          : { key: f.key, name: f.name, state: "refused", reason: r.reason };
      return { ...state, files: state.files.map((f) => (f.key === action.key ? done(f) : f)) };
    }
    case "fileRemove":
      return { ...state, files: state.files.filter((f) => f.key !== action.key) };
    case "delta":
      return state.pending ? { ...state, partial: state.partial + action.text } : state;
    case "answer": {
      if (!state.pending) return state; // the visitor cleared the conversation while it was answering
      const { status, reply, offerContact } = action.result;
      const entry: Entry = status === "ok" ? { id, from: "bot", text: reply } : { id, from: "notice", notice: status };
      const offer = status === "ok" ? offerContact : OFFER_ON.includes(status);
      // a new offer moves the button down to it; not once the form is open (it would remount and lose what was typed)
      const move = offer && (state.contact.step === "none" || state.contact.step === "offered");
      const contact: Contact = move ? { step: "offered" } : state.contact;
      const contactAt = move ? id : state.contactAt;
      // the resume panel also moves down to a later offer, until it holds a tailored pair
      const resume: Resume | null =
        status === "ok" && action.result.offerResume && !state.resume?.token
          ? { at: id, token: null, company: "", role: "", note: state.resume?.note ?? null }
          : state.resume;
      return { ...state, entries: [...state.entries, entry], pending: false, partial: "", contact, contactAt, resume };
    }
    case "openForm":
      return { ...state, contact: { step: "form", error: false } };
    case "leadDone": {
      const { status, whatsapp } = action.result;
      const contact: Contact =
        status === "ok"
          ? whatsapp ? { step: "sent", whatsapp } : { step: "sent" }
          : status === "invalid" ? { step: "form", error: true } : { step: "email" };
      return { ...state, contact };
    }
    case "resumeDone": {
      if (!state.resume) return state;
      const { status, token, company, role } = action.result;
      const tailored = status === "ok" && token ? { token, company, role } : { token: state.resume.token, company: state.resume.company, role: state.resume.role };
      return { ...state, resume: { ...state.resume, ...tailored, note: status } };
    }
    case "clear":
      return initial;
  }
}
