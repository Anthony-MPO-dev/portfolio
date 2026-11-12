import { type CSSProperties, type FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { CHAT_ASK } from "@/lib/events";
import { type Fact, getFacts, type Hit, searchFacts } from "./api";
import { copy, type Lang, LANGS } from "./copy";
import { scaler } from "./map";
import { getSound, setSound, useTypewriter } from "./typing";
import "./fact-search.css";

// "Search what the bot knows" on the home, after "How this bot is tested" (direction B, chosen by the author on 12/11):
// a terminal prompt with a green cursor, the map of every fact where the question lands and draws lines to the 5
// closest, and those 5 typed in like the bot writing them (with quiet key clicks). The search runs on the server
// (api.ts); the map loads when the section comes near the screen, and again with a search if it failed. English by
// default, with EN, PT and FR in the section (its lang follows). "Ask the bot" hands the question to the chat.
// Public API: FactSearch. Used by: app/routes/home.tsx.
// Tests: the logic is in api.ts, map.ts and copy.ts (their tests); the section itself was checked in Chrome.

const CHAT = import.meta.env.VITE_CHAT === "1";
const css = (o: Record<string, string | number>) => o as CSSProperties;

type Found = { n: number; q: string; hits: Hit[]; x: number; y: number };
type State = { status: "idle" | "searching" | "invalid" | "rate_limited" | "offline" } | ({ status: "ok" } & Found);

export function FactSearch() {
  const [lang, setLang] = useState<Lang>("en");
  const t = copy[lang];
  const [facts, setFacts] = useState<Fact[] | null>(null);
  const [state, setState] = useState<State>({ status: "idle" });
  const [sound, setSoundOn] = useState(true);
  const section = useRef<HTMLElement>(null);
  const searches = useRef(0);

  useEffect(() => {
    setSoundOn(getSound());
    const near = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return;
        near.disconnect();
        getFacts().then(setFacts);
      },
      { rootMargin: "800px 0px" },
    );
    if (section.current) near.observe(section.current);
    return () => near.disconnect();
  }, []);

  async function ask(q: string) {
    if (!q.trim() || state.status === "searching") return;
    setState({ status: "searching" });
    const [result, map] = await Promise.all([searchFacts(q.trim()), facts ? facts : getFacts()]);
    if (map && !facts) setFacts(map);
    if (result.status === "ok" && map) setState({ ...result, n: ++searches.current, q: q.trim() });
    else setState({ status: result.status === "ok" || result.status === "unavailable" ? "offline" : result.status });
  }

  const found = state.status === "ok" ? state : null;
  const byId = useMemo(() => new Map((facts ?? []).map((f) => [f.id, f])), [facts]);
  const top = found ? found.hits.flatMap((h) => (byId.has(h.id) ? [{ ...h, fact: byId.get(h.id)! }] : [])) : [];
  const status =
    state.status === "searching"
      ? t.searching
      : state.status === "ok"
        ? t.done(facts?.length ?? 0)
        : state.status === "idle"
          ? ""
          : t[state.status];

  return (
    <section ref={section} className="fact-search typed" aria-label={t.label} lang={lang}>
      <h2 className="label">{t.label}</h2>
      <div className="fs-side">
        <div className="fs-langs" role="group" aria-label={t.language}>
          {LANGS.map((l) => (
            <button key={l.id} type="button" aria-pressed={l.id === lang} title={l.name} onClick={() => setLang(l.id)}>
              {l.label}
            </button>
          ))}
        </div>
        <p className="fs-lead">{t.lead(facts?.length)}</p>
        <Prompt placeholder={t.placeholder} button={t.search} onAsk={ask} chips={t.chips} />
        <div className="fs-status-row">
          <p className="fs-status" aria-live="polite">
            {status}
          </p>
          <button
            type="button"
            className="fs-sound"
            aria-pressed={sound}
            onClick={() => {
              setSound(!sound);
              setSoundOn(!sound);
            }}
          >
            {t.sound(sound)}
          </button>
        </div>
      </div>
      {facts && <FactMap facts={facts} found={found} top={top} label={t.mapLabel(facts.length)} caption={t.caption} />}
      {found && top.length > 0 && <Results key={found.n} found={found} top={top} t={t} />}
      <p className="fs-honest">{t.honest}</p>
    </section>
  );
}

function Prompt({ placeholder, button, onAsk, chips }: { placeholder: string; button: string; onAsk: (q: string) => void; chips: string[] }) {
  const [q, setQ] = useState("");
  const [at, setAt] = useState(0); // where the caret is, so the green cursor sits there
  const input = useRef<HTMLInputElement>(null);
  const sync = () => setAt(input.current?.selectionStart ?? q.length);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    onAsk(q);
  };
  return (
    <>
      <form onSubmit={submit} role="search" className="fs-prompt">
        <span className="fs-ps" aria-hidden="true">
          &gt;
        </span>
        <div className="fs-field">
          <label className="num-sr" htmlFor="fs-q">
            {placeholder}
          </label>
          <input
            id="fs-q"
            ref={input}
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setAt(e.target.selectionStart ?? e.target.value.length);
            }}
            onSelect={sync}
            onKeyUp={sync}
            onClick={sync}
            maxLength={200}
            autoComplete="off"
            spellCheck={false}
          />
          <span className="fs-mirror" aria-hidden="true">
            <span>{q.slice(0, at)}</span>
            <i className="fs-cur">_</i>
            {!q && <span className="fs-ph">{placeholder}</span>}
          </span>
        </div>
        <button type="submit">{button}</button>
      </form>
      <div className="fs-chips">
        {chips.map((c) => (
          <button
            key={c}
            type="button"
            onClick={() => {
              setQ(c);
              setAt(c.length);
              onAsk(c);
            }}
          >
            {c}
          </button>
        ))}
      </div>
    </>
  );
}

type Copy = (typeof copy)[Lang];
type Shown = Hit & { fact: Fact };

// The 5 closest, typed one after the other with the green cursor at the end of the one being written. Every item is
// in the page from the start (screen readers get each whole text at once); the ones still waiting are invisible.
// "Ask the bot" comes when the typing ends.
function Results({ found, top, t }: { found: Found; top: Shown[]; t: Copy }) {
  const shown = useTypewriter(
    top.map((h) => h.fact.text),
    String(found.n),
  );
  const typing = shown.findIndex((n, i) => n < top[i].fact.text.length);
  return (
    <div className="fs-results">
      {t.factsNote && <p className="fs-note">{t.factsNote}</p>}
      <ol className="fs-list">
        {top.map((h, i) => (
          <li key={h.id} className={typing !== -1 && i > typing ? "fs-wait" : undefined}>
            <b>{i + 1}</b>
            <div>
              <p className="fs-meta">
                <span lang="en">{h.fact.section}</span>
                <b>{h.score.toFixed(3)}</b>
              </p>
              <p lang="en">
                <span aria-hidden="true">
                  {h.fact.text.slice(0, shown[i])}
                  {i === typing && <i className="fs-cur">_</i>}
                </span>
                <span className="num-sr">{h.fact.text}</span>
              </p>
            </div>
          </li>
        ))}
      </ol>
      {CHAT && typing === -1 && (
        <div className="fs-ask">
          <button type="button" onClick={() => window.dispatchEvent(new CustomEvent(CHAT_ASK, { detail: found.q }))}>
            {t.ask(found.q)} <span className="arrow" aria-hidden="true">&rarr;</span>
          </button>
          <p>{t.askNote}</p>
        </div>
      )}
    </div>
  );
}

function FactMap({ facts, found, top, label, caption }: { facts: Fact[]; found: Found | null; top: Shown[]; label: string; caption: string }) {
  const { sx, sy } = useMemo(() => scaler(facts), [facts]);
  const rank = new Set(top.map((h) => h.id));
  const [qx, qy] = found ? [sx(found.x), sy(found.y)] : [0, 0];
  return (
    <figure className="fs-map">
      <svg viewBox="0 0 100 100" role="img" aria-label={label} key={found?.n ?? "idle"}>
        {top.map((h, i) => (
          <line key={h.id} x1={qx} y1={qy} x2={sx(h.fact.x)} y2={sy(h.fact.y)} pathLength={1} className="fs-line" style={css({ "--i": i })} />
        ))}
        {facts.map((f) => (
          <circle key={f.id} cx={sx(f.x)} cy={sy(f.y)} r={rank.has(f.id) ? 1.5 : 1} className={rank.has(f.id) ? "fs-top" : undefined}>
            <title>{f.text}</title>
          </circle>
        ))}
        {top.map((h, i) => (
          <text key={h.id} x={sx(h.fact.x) + 2} y={sy(h.fact.y) - 1.6} style={css({ "--i": i })}>
            {i + 1}
          </text>
        ))}
        {found && (
          <g className="fs-q">
            <circle cx={qx} cy={qy} r={4} className="fs-ring" />
            <circle cx={qx} cy={qy} r={1.8} />
          </g>
        )}
      </svg>
      <figcaption>{caption}</figcaption>
    </figure>
  );
}
