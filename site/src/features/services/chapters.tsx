import type { CSSProperties } from "react";
import { CountUp } from "@/components/count-up";
import { blockers, intro, payoff, type Source, stall } from "@/content/services";
import { step } from "@/lib/step";

// The case for the service, one screen per chapter (.scene, played once by useReveal): most AI stalls (100 squares,
// 25 lit), why (one bar split 70/20/10), and the payoff once it ships (two ROI bars rising). Every figure carries its
// source as a link. From 1100 px the drawing (.svc-fig) sits left of the words (.svc-words). The base styles are the
// final picture (no JS, reduced motion).
// Public API: StallChapter, BlockersChapter, PayoffChapter. Used by app/routes/services.tsx.

function Sources({ list, note }: { list: Source[]; note?: string }) {
  return (
    <p className="svc-src">
      {note && <>{note} </>}
      {intro.sources}{" "}
      {list.map((s, i) => (
        <span key={s.url}>
          {i > 0 && ", "}
          <a href={s.url}>{s.name}</a>
        </span>
      ))}
      .
    </p>
  );
}

export function StallChapter() {
  return (
    <section className="scene" aria-label="Most AI stalls">
      <div className="stage svc-stage svc-pair">
        <p className="svc-kicker">{stall.kicker}</p>
        <div className="svc-fig">
          <div className="svc-waffle" role="img" aria-label={`${stall.value} of 100 squares lit`}>
            {Array.from({ length: 100 }, (_, i) => (
              <span key={i} className={i < stall.value ? "lit" : undefined} style={{ "--d": i } as CSSProperties} />
            ))}
          </div>
        </div>
        <div className="svc-words">
          <p className="svc-say">
            {stall.lead} <b>{stall.value}%</b> {stall.text}
          </p>
          <p className="svc-also">{stall.also}</p>
          <Sources list={stall.sources} />
        </div>
      </div>
    </section>
  );
}

export function BlockersChapter() {
  return (
    <section className="scene" aria-label="Why it stalls">
      <div className="stage svc-stage svc-pair">
        <p className="svc-kicker">{blockers.kicker}</p>
        <div className="svc-fig">
          <div
            className="svc-split"
            role="img"
            aria-label={blockers.parts.map((p) => `${p.label} ${p.value}%`).join(", ")}
          >
            {blockers.parts.map((p, k) => (
              <span
                key={p.label}
                className={k === 0 ? "first" : undefined}
                style={{ "--w": p.value, ...step(k * 2) } as CSSProperties}
              />
            ))}
          </div>
          <ul className="svc-key">
            {blockers.parts.map((p, k) => (
              <li key={p.label} className={k === 0 ? "first" : undefined}>
                <b>{p.value}%</b> {p.label}
              </li>
            ))}
          </ul>
        </div>
        <div className="svc-words">
          <p className="svc-say">{blockers.text}</p>
          <Sources list={blockers.sources} />
        </div>
      </div>
    </section>
  );
}

export function PayoffChapter() {
  const top = Math.max(...payoff.studies.map((s) => s.roi));
  return (
    <section className="scene" aria-label="When it ships, it pays back">
      <div className="stage svc-stage svc-pair">
        <p className="svc-kicker">{payoff.kicker}</p>
        <div className="svc-fig svc-roi">
          {payoff.studies.map((s, k) => (
            <div key={s.label}>
              <span
                className="svc-roi-bar"
                style={{ "--h": s.roi / top, ...step(k * 2) } as CSSProperties}
                aria-hidden="true"
              />
              <b>
                <CountUp text={`${s.roi}%`} delay={300 + k * 280} ms={1100} />
              </b>
              <small>
                {payoff.roiLabel} {s.label}
              </small>
            </div>
          ))}
        </div>
        <div className="svc-words">
          <p className="svc-say">{payoff.text}</p>
          <Sources list={payoff.sources} note={payoff.note} />
        </div>
      </div>
    </section>
  );
}
