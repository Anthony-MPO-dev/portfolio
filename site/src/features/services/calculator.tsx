import { type CSSProperties, useEffect, useRef, useState } from "react";
import { calculator as copy } from "@/content/services";
import { onEntry, reducedMotion } from "@/lib/entry";
import { WORK_WEEKS, clampInput, fullTimePeople, hoursBack, monthlyHours, parseRate } from "./hours";

// The closing chapter: the visitor's own numbers in, the hours their team gets back out, as a big figure that counts
// to each new total and a 12-month chart that grows again. The fields keep what the visitor typed; the maths uses
// the cleaned numbers (hours.ts) and the field settles on them when it loses focus. The state lives here, so typing
// re-renders only this chapter.
// Public API: Calculator. Used by app/routes/services.tsx.

const fmt = (n: number) => new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(n);

export function Calculator({ mail }: { mail: string }) {
  const [people, setPeople] = useState("5");
  const [hours, setHours] = useState("8");
  const [cut, setCut] = useState(50);
  const [rate, setRate] = useState("");
  const total = hoursBack({
    people: clampInput(people, 1, 500),
    hoursPerWeek: clampInput(hours, 1, 40),
    cutPercent: cut,
  });
  const fte = fullTimePeople(total);
  const perHour = parseRate(rate);

  return (
    <section className="scene svc-calc" aria-label="Your numbers">
      <div className="stage svc-stage">
        <p className="svc-kicker">{copy.kicker}</p>
        <div className="svc-calc-grid">
          <div className="svc-fields">
            <label>
              <span>{copy.people}</span>
              <input
                type="number"
                inputMode="numeric"
                min={1}
                max={500}
                value={people}
                onChange={(e) => setPeople(e.target.value)}
                onBlur={() => setPeople(String(clampInput(people, 1, 500)))}
              />
            </label>
            <label>
              <span>{copy.hours}</span>
              <input
                type="number"
                inputMode="numeric"
                min={1}
                max={40}
                value={hours}
                onChange={(e) => setHours(e.target.value)}
                onBlur={() => setHours(String(clampInput(hours, 1, 40)))}
              />
            </label>
            <label className="svc-range">
              <span>
                {copy.cut}: <b>{cut}%</b>
              </span>
              <input
                type="range"
                min={10}
                max={90}
                step={5}
                value={cut}
                onChange={(e) => setCut(Number(e.target.value))}
              />
              <small>{copy.cutNote}</small>
            </label>
            <label>
              <span>{copy.rate}</span>
              <input inputMode="decimal" placeholder="e.g. 50" value={rate} onChange={(e) => setRate(e.target.value)} />
            </label>
          </div>
          <div className="svc-out" aria-live="polite">
            <p className="svc-big">
              <Ticker value={total} />
            </p>
            <p className="svc-unit">{copy.result}</p>
            <p className="svc-sub">
              {fte >= 0.1 && (
                <>
                  About <b>{fmt(fte)}</b> full-time {fte === 1 ? "person" : "people"} free for other work.{" "}
                </>
              )}
              {perHour !== null && (
                <>
                  Worth about <b>{fmt(Math.round(total * perHour))}</b> a year, in your currency.
                </>
              )}
            </p>
            <MonthBars total={total} />
          </div>
        </div>
        <p className="svc-terms">{copy.terms}</p>
        <a className="svc-cta" href={mail}>
          {copy.cta}{" "}
          <span className="arrow" aria-hidden="true">
            &rarr;
          </span>
        </a>
      </div>
    </section>
  );
}

// One series (hours back), so the caption names it and there is no legend. The bars grow with scaleY only; the key
// replays the growth when the total changes. Hover shows each month's figure.
function MonthBars({ total }: { total: number }) {
  return (
    <figure className="svc-months" aria-label={`Hours back piling up over 12 months, reaching ${fmt(total)}.`}>
      <div className="svc-months-plot" key={total}>
        {monthlyHours(total).map((h, i) => (
          <span
            key={i}
            title={`Month ${i + 1}: ${fmt(h)} hours`}
            style={{ "--h": (i + 1) / 12, "--i": i } as CSSProperties}
          />
        ))}
      </div>
      <figcaption>
        <span>Month 1</span>
        <span>
          {copy.chart} ({WORK_WEEKS} working weeks)
        </span>
        <span>Month 12</span>
      </figcaption>
    </figure>
  );
}

// The total, counting from the last figure shown to the new one in 0.6 s (text only): the first time from zero, when
// it comes into view; after that, on every change. Final figure in the HTML.
function Ticker({ value }: { value: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const shown = useRef(0);
  const seen = useRef(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || reducedMotion()) return;
    let frame = 0;
    const run = () => {
      const from = shown.current;
      const start = performance.now();
      const tick = (now: number) => {
        const t = Math.min(1, (now - start) / 600);
        shown.current = Math.round(from + (value - from) * (1 - (1 - t) ** 3));
        el.textContent = fmt(shown.current);
        if (t < 1) frame = requestAnimationFrame(tick);
      };
      frame = requestAnimationFrame(tick);
    };
    let stop = () => {};
    if (seen.current) run();
    else {
      el.textContent = "0";
      stop = onEntry(el, () => {
        seen.current = true;
        run();
      });
    }
    return () => {
      stop();
      cancelAnimationFrame(frame);
    };
  }, [value]);
  return <span ref={ref}>{fmt(value)}</span>;
}
