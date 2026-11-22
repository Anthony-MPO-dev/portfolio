import { useEffect, useReducer, useRef, useState, type KeyboardEvent } from "react";
import { contact } from "@/content/profile";
import { conversation } from "./api";
import { CHAT_ASK } from "@/lib/events";
import type { Lang } from "@/lib/lang";
import { humanToken } from "./human";
import { copy } from "./copy";
import { LeadForm } from "./lead-form";
import { initial, reduce, type Action, type Entry, type State } from "./state";
import "./chat.css";

// Chat: a launcher in the corner that opens the panel (a full page over the site on phones). Replies keep their
// line breaks; the fixed text follows the page's language (copy.ts). Mounted by app/root.tsx only when the build
// sets VITE_CHAT=1. Tests: state.test.ts, api.test.ts (the session rules, `conversation`).
type Copy = (typeof copy)[Lang];
const MAX = 500;
const FILES = 3; // per message, as the API allows
const ACCEPT = "image/png,image/jpeg,image/webp,application/pdf,.xlsx,.csv";

export function Chat({ lang }: { lang: Lang }) {
  const t = copy[lang];
  const [open, setOpen] = useState(false);
  const [state, dispatch] = useReducer(reduce, initial);
  const [draft, setDraft] = useState("");
  const launcher = useRef<HTMLButtonElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const log = useRef<HTMLDivElement>(null);
  const opened = useRef(false);
  const inflight = useRef<AbortController | null>(null);
  const picker = useRef<HTMLInputElement>(null);
  const fileKey = useRef(0);
  const proofBox = useRef<HTMLDivElement>(null); // where Cloudflare's check shows, only if it wants a click
  const proof = async () => {
    // the panel may have just opened ("Ask the bot"): let it show before Cloudflare's check goes in it
    for (let i = 0; i < 3 && proofBox.current?.closest("[hidden]"); i++) await new Promise((r) => requestAnimationFrame(r));
    return proofBox.current ? humanToken(proofBox.current) : undefined;
  };
  const [talk] = useState(() => conversation(proof)); // the session and its browser proof (api.ts)
  const uploading = state.files.some((f) => f.state === "uploading");
  const room = FILES - state.files.filter((f) => f.state !== "refused").length;

  useEffect(() => {
    document.documentElement.classList.toggle("chat-open", open);
    if (open) input.current?.focus();
    else if (opened.current) launcher.current?.focus();
    opened.current ||= open;
  }, [open]);

  useEffect(() => {
    log.current?.scrollTo({ top: log.current.scrollHeight });
  }, [open, state.entries.length, state.pending, state.partial, state.contact.step]);

  // Says whether the text went. A ref, not state.pending: a double tap sees the first send at once, so only one
  // request goes out.
  function send(text: string): boolean {
    if (!text.trim() || inflight.current || uploading) return false;
    const files = state.files.flatMap((f) => (f.state === "ready" ? [f.id] : []));
    dispatch({ type: "send", text });
    const controller = (inflight.current = new AbortController());
    const onDelta = (piece: string) => dispatch({ type: "delta", text: piece });
    talk
      .send(text.trim(), lang, { files, onDelta, signal: controller.signal })
      .then((result) => dispatch({ type: "answer", result }))
      .finally(() => (inflight.current = null)); // a cleared conversation's request still holds it until it has settled
    return true;
  }

  // only the draft's own send empties it: a suggestion or "Ask the bot" leaves what the visitor was typing
  function sendDraft() {
    if (send(draft)) setDraft("");
  }

  // Each file uploads on its own request, so they are converted side by side (the first one alone while there is no
  // session yet: talk.upload).
  async function pick(list: FileList | null) {
    const files = Array.from(list ?? []).slice(0, room);
    const keys = files.map((file) => {
      const key = ++fileKey.current;
      dispatch({ type: "fileStart", key, name: file.name });
      return key;
    });
    if (picker.current) picker.current.value = "";
    await talk.upload(files, (i, result) => dispatch({ type: "fileDone", key: keys[i], result }));
  }

  // "Ask the bot" from the fact search: open the panel and send the question as if it were typed here
  const sendLatest = useRef(send);
  useEffect(() => {
    sendLatest.current = send;
  });
  useEffect(() => {
    const onAsk = (event: Event) => {
      const question = (event as CustomEvent<unknown>).detail;
      if (typeof question !== "string" || !question.trim()) return;
      setOpen(true);
      sendLatest.current(question);
    };
    window.addEventListener(CHAT_ASK, onAsk);
    return () => window.removeEventListener(CHAT_ASK, onAsk);
  }, []);

  function onKey(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendDraft();
    }
  }

  return (
    <>
      <button
        ref={launcher}
        type="button"
        className="chat-launcher"
        hidden={open}
        aria-expanded={open}
        aria-controls="chat"
        onClick={() => setOpen(true)}
      >
        {t.launcher}
      </button>
      <section
        id="chat"
        className="chat"
        hidden={!open}
        role="dialog"
        aria-label={t.title}
        onKeyDown={(e) => e.key === "Escape" && setOpen(false)}
      >
        <header className="chat-head">
          <div>
            <p className="chat-title">{t.title}</p>
            <p className="chat-sub">{t.sub}</p>
          </div>
          <div className="chat-actions">
            {state.entries.length > 0 && (
              <button
                type="button"
                className="chat-btn"
                onClick={() => {
                  inflight.current?.abort();
                  dispatch({ type: "clear" });
                  talk.clear();
                }}
              >
                {t.clear}
              </button>
            )}
            <button type="button" className="chat-btn" onClick={() => setOpen(false)}>
              {t.close}
            </button>
          </div>
        </header>

        <div className="chat-log" ref={log} aria-live="polite" aria-busy={state.pending}>
          {state.entries.length === 0 && (
            <div className="chat-intro">
              <h2>{t.intro}</h2>
              <div className="chat-suggest">
                {t.suggestions.map((q) => (
                  <button key={q} type="button" onClick={() => send(q)}>
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}
          {state.entries.map((entry) => (
            <Message key={entry.id} entry={entry} t={t} />
          ))}
          {state.partial && <Message entry={{ id: -1, from: "bot", text: state.partial }} t={t} />}
          {state.pending && !state.partial && (
            <p className="chat-typing" role="status" aria-label={t.typing}>
              <span />
              <span />
              <span />
            </p>
          )}
          <ContactPanel state={state} lang={lang} dispatch={dispatch} lead={talk.lead} />
        </div>

        <div ref={proofBox} className="chat-proof" />
        <form
          className="chat-composer"
          onSubmit={(e) => {
            e.preventDefault();
            sendDraft();
          }}
        >
          {state.files.length > 0 && (
            <ul className="chat-files">
              {state.files.map((f) => (
                <li key={f.key} className={`chat-file ${f.state}`}>
                  <span className="chat-file-name">{f.name}</span>
                  <span className="chat-file-note">
                    {f.state === "uploading" ? t.files.reading : f.state === "ready" ? f.summary : t.files.refused[f.reason]}
                  </span>
                  <button
                    type="button"
                    aria-label={`${t.files.remove} ${f.name}`}
                    onClick={() => dispatch({ type: "fileRemove", key: f.key })}
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          )}
          <textarea
            ref={input}
            rows={1}
            maxLength={MAX}
            value={draft}
            placeholder={t.placeholder}
            aria-label={t.placeholder}
            enterKeyHint="send"
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKey}
          />
          <div className="chat-bar">
            <input ref={picker} type="file" accept={ACCEPT} multiple hidden onChange={(e) => pick(e.target.files)} />
            <button
              type="button"
              className="chat-attach"
              disabled={state.pending || room < 1}
              aria-label={t.files.attach}
              title={t.files.attach}
              onClick={() => picker.current?.click()}
            >
              <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
                <path
                  d="M21 11.5 12.5 20a5 5 0 0 1-7-7L14 4.5a3.5 3.5 0 0 1 5 5L10.5 18a2 2 0 0 1-3-3l8-8"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.6"
                />
              </svg>
            </button>
            {draft.length > MAX - 100 && (
              <span className="chat-count">
                {draft.length}/{MAX}
              </span>
            )}
            <button type="submit" className="chat-send" disabled={!draft.trim() || state.pending || uploading}>
              {t.send}
            </button>
          </div>
        </form>
        <p className="chat-privacy">{t.privacy}</p>
      </section>
    </>
  );
}

function Message({ entry, t }: { entry: Entry; t: Copy }) {
  if (entry.from === "notice") return <p className="chat-notice">{t.notices[entry.notice]}</p>;
  return (
    <div className={`chat-msg ${entry.from}`}>
      <p className="chat-who">{entry.from === "you" ? t.you : t.bot}</p>
      <p className="chat-text">{entry.text}</p>
      {entry.files && <p className="chat-sent-files">{entry.files.join(", ")}</p>}
    </div>
  );
}

type Lead = ReturnType<typeof conversation>["lead"];

function ContactPanel({ state, lang, dispatch, lead }: { state: State; lang: Lang; dispatch: (a: Action) => void; lead: Lead }) {
  const t = copy[lang];
  const c = state.contact;
  switch (c.step) {
    case "none":
      return null;
    case "offered":
      return (
        <button type="button" className="chat-send chat-talk" onClick={() => dispatch({ type: "openForm" })}>
          {t.talk}
        </button>
      );
    case "form":
      return <LeadForm lang={lang} error={c.error} submit={lead} onDone={(result) => dispatch({ type: "leadDone", result })} />;
    case "sent":
      return c.whatsapp ? (
        <p className="chat-notice">
          {t.sentHiring} <a href={`https://wa.me/${c.whatsapp.replace(/\D/g, "")}`}>{c.whatsapp}</a>
        </p>
      ) : (
        <p className="chat-notice">{t.sentProject}</p>
      );
    case "email":
      return (
        <p className="chat-notice">
          {t.emailFallback} <a href={`mailto:${contact.email}`}>{contact.email}</a>.
        </p>
      );
  }
}
