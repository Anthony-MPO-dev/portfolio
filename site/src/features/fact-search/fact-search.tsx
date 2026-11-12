import { type CSSProperties, type FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { type Fact, getFacts, type Hit, searchFacts } from "./api";
import { copy, type Lang, LANGS } from "./copy";
import { scaler } from "./map";
import { getSound, setSound, useTypewriter } from "./typing";
import "./fact-search.css";

// "Search what the bot knows" on the home, after "How this bot is tested" (direction B, chosen by the author on 12/11):
// a terminal prompt with a green cursor, the 5 closest facts typed in like the bot writing them (with quiet key
// clicks), and the map of every fact where the question lands and draws lines to them. The search runs on the
// server (api.ts); the map loads with the page's first visit to it. English by default, with EN, PT and FR in the
// section. "Ask the bot" hands the question to the chat.
// Public API: FactSearch. Used by: app/routes/home.tsx.

const LOW = 0.78; // below this best score nothing in the facts is near (measured 12/11 on the search set)
const CHAT = import.meta.env.VITE_CHAT === "1";
const css = (o: Record<string, string | number>) => o as CSSProperties;

type State =
  | { status: "idle" | "searching" | "invalid" | "rate_limited" | "offline" | "unavailable" }
  | { status: "ok"; q: string; hits: Hit[]; x: number; y: number };

export function FactSearch() {
  const [lang, setLang] = useState<Lang>("en");
  const t = copy[lang];
  const [facts, setFacts] = useState<Fact[] | null>(null);
  const [state, setState] = useState<State>({ status: "idle" });
  const [sound, setSoundOn] = useState(true);
  const count = facts?.length ?? 66;

  useEffect(() => {
    getFacts().then(setFacts);
    setSoundOn(getSound());
  }, []);

  async function ask(q: string) {
    if (!q.trim() || state.status === "searching") return;
    setState({ status: "searching" });
    const result = await searchFacts(q.trim());
    setState(result.status === "ok" ? { ...result, q: q.trim() } : { status: result.status });
  }

  const found = state.status === "ok" ? state : null;
  const best = found ? Math.max(...found.hits.map((h) => h.score)) : 1;
  const refused = { invalid: t.invalid, rate_limited: t.rate_limited, offline: t.offline, unavailable: t.offline };
  const status =
    state.status === "searching"
      ? t.searching
      : state.status === "ok"
        ? best < LOW
          ? t.nothing
          : t.done(count)
        : state.status === "idle"
          ? ""
          : refused[state.status];

  return (
    <section className="fact-search typed" aria-label={t.label}>
      <h2 className="label">{t.label}</h2>
      <div className="fs-side">
        <div className="fs-langs" role="group" aria-label={t.language}>
          {LANGS.map((l) => (
            <button key={l.id} type="button" aria-pressed={l.id === lang} title={l.name} onClick={() => setLang(l.id)}>
              {l.label}
            </button>
          ))}
        </div>
        <p className="fs-lead">{t.lead(count)}</p>
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
        {found && facts && <Results key={found.q} found={found} facts={facts} t={t} />}
      </div>
      {facts && <FactMap facts={facts} found={found} label={t.mapLabel(count)} caption={t.caption} />}
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

// The 5 closest, typed one after the other with the green cursor at the end of the one being written; screen readers
// get each whole text at once. "Ask the bot" comes when the typing ends.
function Results({ found, facts, t }: { found: { q: string; hits: Hit[] }; facts: Fact[]; t: Copy }) {
  const byId = useMemo(() => new Map(facts.map((f) => [f.id, f])), [facts]);
  const hits = found.hits.flatMap((h) => (byId.has(h.id) ? [{ ...h, fact: byId.get(h.id)! }] : []));
  const shown = useTypewriter(
    hits.map((h) => h.fact.text),
    found.q,
  );
  const typing = shown.findIndex((n, i) => n < hits[i].fact.text.length);
  return (
    <>
      {t.factsNote && <p className="fs-note">{t.factsNote}</p>}
      <ol className="fs-list">
        {hits.map((h, i) =>
          i > 0 && typing !== -1 && typing < i ? null : (
            <li key={h.id}>
              <b>{i + 1}</b>
              <div>
                <p className="fs-meta">
                  <span>{h.fact.section}</span>
                  <b>{h.score.toFixed(3)}</b>
                </p>
                <p>
                  <span aria-hidden="true">
                    {h.fact.text.slice(0, shown[i])}
                    {i === typing && <i className="fs-cur">_</i>}
                  </span>
                  <span className="num-sr">{h.fact.text}</span>
                </p>
              </div>
            </li>
          ),
        )}
      </ol>
      {CHAT && typing === -1 && (
        <div className="fs-ask">
          <button type="button" onClick={() => window.dispatchEvent(new CustomEvent("chat:ask", { detail: found.q }))}>
            {t.ask(found.q)} <span className="arrow" aria-hidden="true">&rarr;</span>
          </button>
          <p>{t.askNote}</p>
        </div>
      )}
    </>
  );
}

function FactMap({ facts, found, label, caption }: { facts: Fact[]; found: { q: string; hits: Hit[]; x: number; y: number } | null; label: string; caption: string }) {
  const { sx, sy } = useMemo(() => scaler(facts), [facts]);
  const byId = useMemo(() => new Map(facts.map((f) => [f.id, f])), [facts]);
  const top = found ? found.hits.filter((h) => byId.has(h.id)) : [];
  const rank = new Map(top.map((h, i) => [h.id, i + 1]));
  const [qx, qy] = found ? [sx(found.x), sy(found.y)] : [0, 0];
  return (
    <figure className="fs-map">
      <svg viewBox="0 0 100 100" role="img" aria-label={label} key={found?.q ?? "idle"}>
        {top.map((h, i) => {
          const f = byId.get(h.id)!;
          return <line key={h.id} x1={qx} y1={qy} x2={sx(f.x)} y2={sy(f.y)} pathLength={1} className="fs-line" style={css({ "--i": i })} />;
        })}
        {facts.map((f) => (
          <circle key={f.id} cx={sx(f.x)} cy={sy(f.y)} r={rank.has(f.id) ? 1.5 : 1} className={rank.has(f.id) ? "fs-top" : undefined}>
            <title>{f.text}</title>
          </circle>
        ))}
        {top.map((h, i) => {
          const f = byId.get(h.id)!;
          return (
            <text key={h.id} x={sx(f.x) + 2} y={sy(f.y) - 1.6} style={css({ "--i": i })}>
              {i + 1}
            </text>
          );
        })}
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
