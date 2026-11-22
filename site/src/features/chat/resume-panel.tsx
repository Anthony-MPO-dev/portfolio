import { type CSSProperties, type FormEvent, useState } from "react";
import type { Lang } from "@/lib/lang";
import { downloadPdf, requestResume, type PdfKind, type ResumeResult } from "./api";
import { copy } from "./copy";
import { rainBurst } from "./rain-burst";
import type { Resume } from "./state";

// The resume panel, under the answer that offered it: the two PDFs (the standard pair until one is tailored), each
// button showing the share downloaded and the green rain when the file is saved, and the job post field that tailors
// both. Public API: ResumePanel. Used by: chat.tsx. State: state.ts (resume); calls: api.ts (requestResume,
// downloadPdf). Tests: the reducer and client tests (state.test.ts, api.test.ts) and the browser run on the local copy
// (local/compose.yaml, local/e2e.py).
type Copy = (typeof copy)[Lang]["resume"];
const MAX_JOB = 8000;
const NAMES: Record<PdfKind, string> = { resume: "Anthony_Muniz_Resume.pdf", letter: "Anthony_Muniz_Cover_Letter.pdf" };

export function ResumePanel({ resume, lang, onDone }: { resume: Resume; lang: Lang; onDone: (result: ResumeResult) => void }) {
  const t = copy[lang].resume;
  const [job, setJob] = useState("");
  const [busy, setBusy] = useState(false);
  const token = resume.token ?? `standard-${lang}`;

  async function tailor(event: FormEvent) {
    event.preventDefault();
    if (!job.trim() || busy) return;
    setBusy(true);
    onDone(await requestResume(job, lang));
    setBusy(false);
  }

  const named = resume.note === "ok" && resume.company && resume.role;
  const done = named ? t.tailoredFor.replace("{role}", resume.role).replace("{company}", resume.company) : resume.note ? t.notes[resume.note] : "";
  const note = busy ? t.tailoring : done; // a screen reader hears that it's working, then how it ended
  return (
    <div className="chat-resume">
      <p className="chat-who">{t.title}</p>
      <p className="chat-resume-intro">{t.intro}</p>
      <div className="chat-resume-files">
        {/* keyed by the pair, so a new pair starts its buttons over */}
        <Download key={`resume-${token}`} kind="resume" label={t.resume} token={token} t={t} />
        <Download key={`letter-${token}`} kind="letter" label={t.letter} token={token} t={t} />
      </div>
      {/* always in the page, so a screen reader hears each new line */}
      <p className="chat-resume-note" role="status">
        {note}
      </p>
      <form className="chat-resume-job" onSubmit={tailor}>
        <label>
          {t.jobLabel}
          <textarea value={job} maxLength={MAX_JOB} rows={3} placeholder={t.jobPlaceholder} onChange={(e) => setJob(e.target.value)} />
        </label>
        {/* aria-disabled while it works: a disabled button would drop the keyboard focus */}
        <button type="submit" className="chat-send" disabled={!job.trim()} aria-disabled={busy}>
          {busy ? t.tailoring : t.tailor}
        </button>
      </form>
    </div>
  );
}

function Download({ kind, label, token, t }: { kind: PdfKind; label: string; token: string; t: Copy }) {
  const [state, setState] = useState<"idle" | "busy" | "done" | "failed">("idle");
  const [share, setShare] = useState(0);

  async function save() {
    if (state === "busy") return; // a second tap rides on the download already running
    setState("busy");
    setShare(0);
    const file = await downloadPdf(token, kind, setShare);
    if (!file) return setState("failed");
    const url = URL.createObjectURL(file);
    Object.assign(document.createElement("a"), { href: url, download: NAMES[kind] }).click();
    setTimeout(() => URL.revokeObjectURL(url), 10_000);
    setShare(1);
    setState("done");
    rainBurst();
  }

  const status = state === "busy" ? `${Math.round(share * 100)}%` : state === "done" ? t.saved : state === "failed" ? t.failed : "PDF";
  return (
    <button type="button" className={`chat-download ${state}`} aria-busy={state === "busy"} onClick={save} style={{ "--share": share } as CSSProperties}>
      <span className="chat-download-fill" aria-hidden="true" />
      <span>{label}</span>
      <span className="chat-download-status" aria-live="polite">
        {status}
      </span>
    </button>
  );
}
