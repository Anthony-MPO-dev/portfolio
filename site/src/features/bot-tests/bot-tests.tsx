import type { CSSProperties } from "react";
import { CountUp } from "@/components/count-up";
import { botTests, LEAK_DEMO } from "@/content/bot-tests";
import { useLang } from "@/hooks/use-lang";
import { TYPED_IN_MS } from "@/lib/entry";
import { type Lang, LOCALE } from "@/lib/lang";
import { type Run, showcase, spokenIn, summarize } from "./run";
import "./bot-tests.css";

// "How this bot is tested": the last complete golden set run, as the score, one square per question lighting up in
// the order they ran (grouped by kind; each group opens to its questions, marked passed or failed), and a few
// attacks with the bot's real refusal, then how the secret terms are kept out of the repo (and the CI scan that proves
// it, with its link). The run is content/bot-tests.json; until the author's first run writes it, the section is not
// on the page.
// Public API: BotTests. Used by app/routes/home.tsx.

const found = import.meta.glob<Run>("/src/content/bot-tests.json", { eager: true, import: "default" });
const RUN: Run | undefined = Object.values(found)[0];
const SQUARE_MS = 35; // one square after another; the score counts in step with them

const day = (iso: string, lang: Lang) =>
  new Intl.DateTimeFormat(LOCALE[lang], { dateStyle: "medium", timeZone: "UTC" }).format(new Date(`${iso}T00:00:00Z`));
const modelName = (m: string) => m.charAt(0).toUpperCase() + m.slice(1);

export function BotTests() {
  const lang = useLang();
  const copy = botTests[lang];
  if (!RUN) return null;
  const s = summarize(RUN);
  const failed = RUN.cases.filter((c) => !c.passed);
  // the squares start when the section's text has typed in, one every SQUARE_MS
  const timing = { "--start": `${TYPED_IN_MS}ms`, "--each": `${SQUARE_MS}ms` } as CSSProperties;

  return (
    <section className="bot-tests typed" aria-label={copy.label} style={timing}>
      <h2 className="label">{copy.label}</h2>
      <div className="bt-head">
        <p className="bt-score">
          <CountUp text={`${s.passed}/${s.total}`} delay={TYPED_IN_MS} ms={s.total * SQUARE_MS} />
        </p>
        <p className="bt-sub">{copy.passed(day(RUN.date, lang), modelName(RUN.model))}</p>
        <p className="bt-text">{copy.text(s.total)}</p>
      </div>
      <div className="bt-groups">
        {s.groups.map((g) => (
          <details key={g.group} className="bt-group">
            <summary>
              <span>{copy.groups[g.group] ?? g.group}</span>
              <span>
                {g.passed}/{g.cases.length}
              </span>
              <span className="bt-squares" aria-hidden="true">
                {g.cases.map((c) => (
                  <i key={c.id} className={c.passed ? undefined : "fail"} style={{ "--n": c.n } as CSSProperties} />
                ))}
              </span>
            </summary>
            <ul>
              {g.cases.map((c) => (
                <li key={c.id} className={c.passed ? undefined : "fail"}>
                  <span aria-hidden="true">{c.passed ? "✓" : "×"}</span>
                  <span className="num-sr">{c.passed ? copy.pass : copy.fail}: </span>
                  <span lang={spokenIn(c.q)}>{c.q}</span>
                </li>
              ))}
            </ul>
          </details>
        ))}
        {failed.length > 0 && (
          <p className="bt-failed">
            {copy.failed}{" "}
            {failed.map((c, i) => (
              <span key={c.id} lang={spokenIn(c.q)}>
                {i > 0 && " / "}
                {c.q}
              </span>
            ))}
          </p>
        )}
      </div>
      <div className="bt-attacks">
        <h3>{copy.attacks}</h3>
        {showcase(RUN, 3).map((c) => (
          <div key={c.id} className="bt-pair">
            <p className="bt-q" lang={spokenIn(c.q)}>
              {c.q}
            </p>
            <p className="bt-a" lang={spokenIn(c.reply ?? "")}>
              {c.reply}
            </p>
          </div>
        ))}
      </div>
      <p className="bt-note">{copy.note}</p>
      {copy.ci && (
        <p className="bt-note">
          {copy.ci[0]}
          <a href={LEAK_DEMO}>{copy.ci[1]}</a>
          {copy.ci[2]}
        </p>
      )}
    </section>
  );
}
