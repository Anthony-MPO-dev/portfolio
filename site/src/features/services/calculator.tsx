import { type CSSProperties, useEffect, useRef, useState } from "react";
import { calculator as copy } from "@/content/services";
import { onEntry, reducedMotion } from "@/lib/entry";
import { WORK_WEEKS, clampInput, fullTimePeople, hoursBack, monthlyHours, parseRate } from "./hours";

// The closing chapter: the visitor's own numbers in (the page opens on an example and says so), the hours their team
// gets back out, as a big figure that counts to each new total and a 12-month chart that grows again. The fields keep
// what the visitor typed; the maths uses the cleaned numbers (hours.ts) and a field settles on them when it loses
// focus. The state lives here, so typing re-renders only this chapter.
// Public API: Calculator. Used by app/routes/services.tsx.

const NUMBER = new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 });
const fmt = (n: number) => NUMBER.format(n);
const PEOPLE = { min: 1, max: 500 };
const WEEKLY = { min: 1, max: 40 };

export function Calculator({ mail }: { mail: string }) {
  const [people, setPeople] = useState("5");
  const [hours, setHours] = useState("8");
  const [cut, setCut] = useState(50);
  const [rate, setRate] = useState("");
  const total = hoursBack({
    people: clampInput(people, PEOPLE.min, PEOPLE.max),
    hoursPerWeek: clampInput(hours, WEEKLY.min, WEEKLY.max),
    cutPercent: cut,
  });
  const fte = fullTimePeople(total);
  const perHour = parseRate(rate);

  return (
    <section className="scene svc-calc" aria-label="Your numbers">
      <div className="stage svc-stage">
        <p className="svc-kicker">{copy.kicker}</p>
        <p className="svc-example">{copy.example}</p>
        <div className="svc-calc-grid">
          <div className="svc-fields">
            <NumberField label={copy.people} value={people} set={setPeople} range={PEOPLE} />
            <NumberField label={copy.hours} value={hours} set={setHours} range={WEEKLY} />
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
              {fte >= 0.1 && copy.fullTime(fmt(fte), fte === 1)}{" "}
              {perHour !== null && copy.worth(fmt(Math.round(total * perHour)))}
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

type FieldProps = { label: string; value: string; set: (v: string) => void; range: { min: number; max: number } };

function NumberField({ label, value, set, range: { min, max } }: FieldProps) {
  return (
    <label>
      <span>{label}</span>
      <input
        type="number"
        inputMode="numeric"
        min={min}
        max={max}
        value={value}
        onChange={(e) => set(e.target.value)}
        onBlur={() => set(String(clampInput(value, min, max)))}
      />
    </label>
  );
}

// One series (hours back), so the caption names it and there is no legend. The bars grow with scaleY only; the key
// replays the growth when the total changes. Hover shows each month's figure.
function MonthBars({ total }: { total: number }) {
  const [first, last] = copy.months;
  return (
    <figure className="svc-months" aria-label={copy.chartLabel(fmt(total))}>
      <div className="svc-months-plot" key={total}>
        {monthlyHours(total).map((h, i) => (
          <span
            key={i}
            title={copy.monthTitle(i + 1, fmt(h))}
            style={{ "--h": (i + 1) / 12, "--i": i } as CSSProperties}
          />
        ))}
      </div>
      <figcaption>
        <span>{first}</span>
        <span>{copy.chart(WORK_WEEKS)}</span>
        <span>{last}</span>
      </figcaption>
    </figure>
  );
}

// The total, counting from the last figure shown to the new one in 0.6 s: the first time from zero, when it comes
// into view; after that, on every change. Screen readers get only the final figure (.num-sr); the counting digits are
// hidden from them, so a live region never reads the frames.
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
  return (
    <>
      <span className="num-sr">{fmt(value)}</span>
      <span ref={ref} aria-hidden="true">
        {fmt(value)}
      </span>
    </>
  );
}
