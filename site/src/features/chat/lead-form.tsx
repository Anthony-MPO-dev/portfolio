import { useState, type FormEvent } from "react";
import type { Lang } from "@/lib/lang";
import type { conversation, LeadResult } from "./api";
import { copy } from "./copy";

// Contact form shown when the bot offers it: name, company and email required, LinkedIn optional, Hiring or
// Project. The hidden "website" field is the honeypot. The WhatsApp number only ever comes back from the API.
type Submit = ReturnType<typeof conversation>["lead"]; // sends the browser proof when the WhatsApp number needs it

export function LeadForm({ lang, error, submit: send, onDone }: { lang: Lang; error: boolean; submit: Submit; onDone: (r: LeadResult) => void }) {
  const [busy, setBusy] = useState(false);
  const t = copy[lang].form;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const f = new FormData(event.currentTarget);
    const get = (key: string) => String(f.get(key) ?? "").trim();
    const kind = get("kind") === "project" ? "project" : "hiring";
    setBusy(true);
    onDone(await send({ name: get("name"), company: get("company"), email: get("email"), linkedin: get("linkedin"), kind }, get("website"), lang));
    setBusy(false);
  }

  return (
    <form className="chat-lead" onSubmit={submit}>
      <p className="chat-who">{copy[lang].talk}</p>
      <label>
        {t.name}
        {/* focus brings the form into view where it opened, and keeps the keyboard in it */}
        <input name="name" required maxLength={300} autoComplete="name" autoFocus />
      </label>
      <label>
        {t.company}
        <input name="company" required maxLength={300} autoComplete="organization" />
      </label>
      <label>
        {t.email}
        <input name="email" type="email" required maxLength={300} autoComplete="email" />
      </label>
      <label>
        <span>
          {t.linkedin} <span className="chat-optional">({t.optional})</span>
        </span>
        <input name="linkedin" maxLength={300} inputMode="url" placeholder="linkedin.com/in/..." />
        <small>{t.linkedinHint}</small>
      </label>
      <fieldset>
        <legend>{t.kind}</legend>
        <label>
          <input type="radio" name="kind" value="hiring" required /> {t.hiring}
        </label>
        <label>
          <input type="radio" name="kind" value="project" /> {t.project}
        </label>
      </fieldset>
      <input className="chat-hp" name="website" tabIndex={-1} autoComplete="off" aria-hidden="true" />
      {error && <p role="alert">{t.error}</p>}
      <button type="submit" className="chat-send" disabled={busy}>
        {t.submit}
      </button>
    </form>
  );
}
