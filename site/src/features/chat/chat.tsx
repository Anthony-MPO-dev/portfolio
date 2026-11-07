import { useEffect, useReducer, useRef, useState, type KeyboardEvent } from "react";
import { profile } from "@/content/profile";
import { clearConversation, sendMessage, type Lang } from "./api";
import { copy } from "./copy";
import { LeadForm } from "./lead-form";
import { initial, reduce, type Action, type Entry, type State } from "./state";
import "./chat.css";

// Chat: a launcher in the corner that opens the panel (a full page over the site on phones). Replies keep their
// line breaks. Mounted by app/root.tsx only when the build sets VITE_CHAT=1. Tests: state.test.ts, api.test.ts.
const MAX = 500;

export function Chat({ lang }: { lang: Lang }) {
  const [open, setOpen] = useState(false);
  const [state, dispatch] = useReducer(reduce, initial);
  const [draft, setDraft] = useState("");
  const launcher = useRef<HTMLButtonElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const log = useRef<HTMLDivElement>(null);
  const opened = useRef(false);

  useEffect(() => {
    document.documentElement.classList.toggle("chat-open", open);
    if (open) input.current?.focus();
    else if (opened.current) launcher.current?.focus();
    opened.current ||= open;
  }, [open]);

  useEffect(() => {
    log.current?.scrollTo({ top: log.current.scrollHeight });
  }, [state.entries.length, state.pending, state.contact.step]);

  async function send(text: string) {
    if (!text.trim() || state.pending) return;
    dispatch({ type: "send", text });
    setDraft("");
    dispatch({ type: "answer", result: await sendMessage(text.trim(), lang) });
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

          <div className="chat-log" ref={log} aria-live="polite">
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
            {state.pending && (
              <p className="chat-typing" role="status" aria-label={copy.typing}>
                <span />
                <span />
                <span />
              </p>
            )}
            <Contact state={state} lang={lang} dispatch={dispatch} />
          </div>

          <form
            className="chat-composer"
            onSubmit={(e) => {
              e.preventDefault();
              send(draft);
            }}
          >
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
              <button type="button" className="chat-attach" disabled aria-label={copy.attach} title={copy.attach}>
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
              <button type="submit" className="chat-send" disabled={!draft.trim() || state.pending}>
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
    </div>
  );
}

function Contact({ state, lang, dispatch }: { state: State; lang: Lang; dispatch: (a: Action) => void }) {
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
