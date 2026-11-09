import { useCallback, useEffect, useId, useRef, useState } from "react";
import { onEntry, reducedMotion, TYPED_IN_MS } from "@/lib/entry";
import { parseFigure } from "@/lib/count";
import "./fire-figure.css";

// A multiplier figure such as "3x" as a button: when it comes into view, and on every click, it jumps 1x, 2x, 3x,
// throws sparks, and catches fire. The HTML always holds the final figure. With reduced motion it is plain text, since
// there is nothing to replay. Only transform and opacity move.
// Public API: FireFigure. Used by app/routes/home.tsx. Logic tests: lib/count.test.ts.

const SPARKS = Array.from({ length: 18 }, (_, i) => ({
  "--a": `${-160 + ((i * 47) % 140)}deg`, // a spray between up-left and up-right
  "--d": `${0.35 + ((i * 13) % 9) * 0.06}em`,
  "--t": `${(i % 6) * 35}ms`,
})) as React.CSSProperties[];

export function FireFigure({ text }: { text: string }) {
  const id = `fire${useId().replace(/\W/g, "")}`; // the filter id, unique per figure and safe inside url(#...)
  const figure = parseFigure(text);
  const last = figure ? Math.round(figure.value) : 0;
  const [step, setStep] = useState(last);
  const [run, setRun] = useState(0);
  const [still, setStill] = useState(false); // reduced motion, known only in the browser (the HTML is prerendered)
  const ref = useRef<HTMLButtonElement>(null);
  const timers = useRef<number[]>([]);

  const play = useCallback(() => {
    timers.current.forEach(clearTimeout);
    setRun((r) => r + 1);
    setStep(1);
    timers.current = Array.from({ length: last - 1 }, (_, i) => window.setTimeout(() => setStep(i + 2), (i + 1) * 340));
  }, [last]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (reducedMotion()) return setStill(true);
    let wait = 0;
    const stop = onEntry(el, () => (wait = window.setTimeout(play, TYPED_IN_MS)));
    return () => {
      stop();
      clearTimeout(wait);
      timers.current.forEach(clearTimeout);
    };
  }, [play]);

  if (!figure || still) return <p className="figure">{text}</p>;
  const lit = run > 0 && step === last;
  return (
    <button
      ref={ref}
      type="button"
      className="figure fire"
      onClick={play}
      data-run={run > 0 ? "" : undefined}
      data-lit={lit ? "" : undefined}
      aria-label={`${text}. Play the animation again`}
    >
      <span className="fire-flame" aria-hidden="true" key={`flame-${run}`} style={{ filter: `blur(0.025em) url(#${id})` }}>
        <i />
        <i />
      </span>
      {/* heat to colour: the grey's brightness becomes the alpha, so black is transparent, then a table keeps the
          strong heat only and paints it red to white */}
      <svg className="fire-defs" aria-hidden="true">
        <filter id={id} colorInterpolationFilters="sRGB">
          <feColorMatrix values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  1 0 0 0 0" />
          <feComponentTransfer>
            <feFuncR type="table" tableValues="0 0 0.9 1 1 1 1" />
            <feFuncG type="table" tableValues="0 0 0.15 0.4 0.7 0.9 1" />
            <feFuncB type="table" tableValues="0 0 0 0 0.15 0.5 0.95" />
            <feFuncA type="table" tableValues="0 0 0.85 1 1 1 1" />
          </feComponentTransfer>
        </filter>
      </svg>
      <span className="fire-num" aria-hidden="true" key={`num-${run}-${step}`}>
        {figure.prefix}
        {step}
        {figure.suffix}
      </span>
      <span className="fire-sparks" aria-hidden="true" key={`sparks-${run}-${step}`}>
        {run > 0 && step > 1 && SPARKS.slice(0, lit ? SPARKS.length : 6).map((style, i) => <i key={i} style={style} />)}
      </span>
      <span className="fire-hint" aria-hidden="true">
        ↻ replay
      </span>
    </button>
  );
}
