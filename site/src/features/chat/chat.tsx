import { useEffect, useReducer, useRef, useState, type KeyboardEvent } from "react";
import { profile } from "@/content/profile";
import { clearConversation, sendMessage, uploadFile, type Lang } from "./api";
import { copy } from "./copy";
import { LeadForm } from "./lead-form";
import { initial, reduce, type Action, type Entry, type State } from "./state";
import "./chat.css";

// Chat: a launcher in the corner that opens the panel (a full page over the site on phones). Replies keep their
// line breaks. Mounted by app/root.tsx only when the build sets VITE_CHAT=1. Tests: state.test.ts, api.test.ts.
const MAX = 500;
const FILES = 3; // per message, as the API allows
const ACCEPT = "image/png,image/jpeg,image/webp,application/pdf,.xlsx,.csv";

export function Chat({ lang }: { lang: Lang }) {
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
  const hasSession = useRef(false); // the API has set the session cookie (it's HttpOnly, so the page can't see it)
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
  }, [state.entries.length, state.pending, state.partial, state.contact.step]);

  async function send(text: string) {
    // a ref, not state.pending: a double tap sees the first send at once, so only one request goes out
    if (!text.trim() || inflight.current || uploading) return;
    const files = state.files.flatMap((f) => (f.state === "ready" ? [f.id] : []));
    dispatch({ type: "send", text });
    setDraft("");
    const controller = (inflight.current = new AbortController());
    const onDelta = (piece: string) => dispatch({ type: "delta", text: piece });
    try {
      const result = await sendMessage(text.trim(), lang, { files, onDelta, signal: controller.signal });
      hasSession.current = true;
      dispatch({ type: "answer", result });
    } finally {
      inflight.current = null; // a cleared conversation's request still holds it until it has settled
    }
  }

  // Each file uploads on its own request, so they are converted side by side. Without a session yet, the first one
  // goes alone: its answer sets the session cookie, or each upload would start a session of its own.
  async function pick(list: FileList | null) {
    const jobs = Array.from(list ?? [])
      .slice(0, room)
      .map((file) => {
        const key = ++fileKey.current;
        dispatch({ type: "fileStart", key, name: file.name });
        return { key, file };
      });
    if (picker.current) picker.current.value = "";
    const run = async ({ key, file }: { key: number; file: File }) => {
      const result = await uploadFile(file);
      hasSession.current = true;
      dispatch({ type: "fileDone", key, result });
    };
    if (!hasSession.current && jobs.length) await run(jobs.shift()!);
    await Promise.all(jobs.map(run));
  }

  function onKey(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      send(draft);
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
        {copy.launcher}
      </button>
      {open && (
        <section
          id="chat"
          className="chat"
          role="dialog"
          aria-label={copy.title}
          onKeyDown={(e) => e.key === "Escape" && setOpen(false)}
        >
          <header className="chat-head">
            <div>
              <p className="chat-title">{copy.title}</p>
              <p className="chat-sub">{copy.sub}</p>
            </div>
            <div className="chat-actions">
              {state.entries.length > 0 && (
                <button
                  type="button"
                  className="chat-btn"
                  onClick={() => {
                    inflight.current?.abort();
                    hasSession.current = false; // the API forgets the session; the next request starts a new one
                    dispatch({ type: "clear" });
                    clearConversation();
                  }}
                >
                  {copy.clear}
                </button>
              )}
              <button type="button" className="chat-btn" onClick={() => setOpen(false)}>
                {copy.close}
              </button>
            </div>
          </header>

          <div className="chat-log" ref={log} aria-live="polite" aria-busy={state.pending}>
            {state.entries.length === 0 && (
              <div className="chat-intro">
                <h2>{copy.intro}</h2>
                <div className="chat-suggest">
                  {copy.suggestions.map((q) => (
                    <button key={q} type="button" onClick={() => send(q)}>
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {state.entries.map((entry) => (
              <Message key={entry.id} entry={entry} />
            ))}
            {state.partial && <Message entry={{ id: -1, from: "bot", text: state.partial }} />}
            {state.pending && !state.partial && (
              <p className="chat-typing" role="status" aria-label={copy.typing}>
                <span />
                <span />
                <span />
              </p>
            )}
            <ContactPanel state={state} lang={lang} dispatch={dispatch} />
          </div>

          <form
            className="chat-composer"
            onSubmit={(e) => {
              e.preventDefault();
              send(draft);
            }}
          >
            {state.files.length > 0 && (
              <ul className="chat-files">
                {state.files.map((f) => (
                  <li key={f.key} className={`chat-file ${f.state}`}>
                    <span className="chat-file-name">{f.name}</span>
                    <span className="chat-file-note">
                      {f.state === "uploading" ? copy.files.reading : f.state === "ready" ? f.summary : copy.files.refused[f.reason]}
                    </span>
                    <button
                      type="button"
                      aria-label={`${copy.files.remove} ${f.name}`}
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
              placeholder={copy.placeholder}
              aria-label={copy.placeholder}
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
                aria-label={copy.files.attach}
                title={copy.files.attach}
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
                {copy.send}
              </button>
            </div>
          </form>
          <p className="chat-privacy">{copy.privacy}</p>
        </section>
      )}
    </>
  );
}

function Message({ entry }: { entry: Entry }) {
  if (entry.from === "notice") return <p className="chat-notice">{copy.notices[entry.notice]}</p>;
  return (
    <div className={`chat-msg ${entry.from}`}>
      <p className="chat-who">{entry.from === "you" ? copy.you : copy.bot}</p>
      <p className="chat-text">{entry.text}</p>
      {entry.files && <p className="chat-sent-files">{entry.files.join(", ")}</p>}
    </div>
  );
}

function ContactPanel({ state, lang, dispatch }: { state: State; lang: Lang; dispatch: (a: Action) => void }) {
  const c = state.contact;
  switch (c.step) {
    case "none":
      return null;
    case "offered":
      return (
        <button type="button" className="chat-send chat-talk" onClick={() => dispatch({ type: "openForm" })}>
          {copy.talk}
        </button>
      );
    case "form":
      return <LeadForm lang={lang} error={c.error} onDone={(result) => dispatch({ type: "leadDone", result })} />;
    case "sent":
      return c.whatsapp ? (
        <p className="chat-notice">
          {copy.sentHiring} <a href={`https://wa.me/${c.whatsapp.replace(/\D/g, "")}`}>{c.whatsapp}</a>
        </p>
      ) : (
        <p className="chat-notice">{copy.sentProject}</p>
      );
    case "email":
      return (
        <p className="chat-notice">
          {copy.emailFallback} <a href={`mailto:${profile.email}`}>{profile.email}</a>.
        </p>
      );
  }
}
