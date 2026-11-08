import { useCallback, useEffect, useId, useRef, useState } from "react";
import { figureAt, parseFigure } from "./count";
import "./numbers.css";

// The page's big numbers. CountUp counts a figure up from zero, fast, when it comes into view. FireFigure (the "3x")
// is a button: when it comes into view, and on every click, it jumps 1x, 2x, 3x, throws sparks, and catches fire.
// The HTML always holds the final figure (no JS, reduced motion, screen readers); only transform and opacity move,
// except the counting digits, whose box keeps its final width so nothing around them shifts.
// Public API: CountUp, FireFigure. Used by app/routes/home.tsx and the search-fix scene. Logic tests: count.test.ts.

const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

// Calls `run` once, when `el` passes 65% of the screen (the same point as the scenes' entrance).
function onEntry(el: Element, run: () => void) {
  const io = new IntersectionObserver(
    ([entry]) => {
      if (!entry.isIntersecting) return;
      io.disconnect();
      run();
    },
    { rootMargin: "0px 0px -35% 0px" },
  );
  io.observe(el);
  return () => io.disconnect();
}

export function CountUp({ text, ms = 900 }: { text: string; ms?: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    const el = ref.current;
    const figure = parseFigure(text);
    if (!el || !figure || reducedMotion()) return;
    el.style.minWidth = `${el.getBoundingClientRect().width}px`;
    el.textContent = figureAt(figure, 0);
    let frame = 0;
    const stop = onEntry(el, () => {
      const start = performance.now();
      const tick = (now: number) => {
        const progress = (now - start) / ms;
        el.textContent = figureAt(figure, progress);
        if (progress < 1) frame = requestAnimationFrame(tick);
      };
      frame = requestAnimationFrame(tick);
    });
    return () => {
      stop();
      cancelAnimationFrame(frame);
      el.textContent = text;
      el.style.minWidth = "";
    };
  }, [text, ms]);
  return (
    <span className="count">
      <span className="num-sr">{text}</span>
      <span ref={ref} aria-hidden="true">
        {text}
      </span>
    </span>
  );
}

const SPARKS = Array.from({ length: 18 }, (_, i) => ({
  "--a": `${-160 + ((i * 47) % 140)}deg`, // a spray between up-left and up-right
  "--d": `${0.35 + ((i * 13) % 9) * 0.06}em`,
  "--t": `${(i % 6) * 35}ms`,
})) as React.CSSProperties[];
const TYPED_IN_MS = 1000; // the figures section's skeleton is gone by then (home-entrance.css)

export function FireFigure({ text }: { text: string }) {
  const id = `fire${useId().replace(/\W/g, "")}`; // the filter id, unique per figure and safe inside url(#...)
  const figure = parseFigure(text);
  const last = figure ? Math.round(figure.value) : 0;
  const [step, setStep] = useState(last);
  const [run, setRun] = useState(0);
  const ref = useRef<HTMLButtonElement>(null);
  const timers = useRef<number[]>([]);

  const play = useCallback(() => {
    if (reducedMotion()) return;
    timers.current.forEach(clearTimeout);
    setRun((r) => r + 1);
    setStep(1);
    timers.current = Array.from({ length: last - 1 }, (_, i) => window.setTimeout(() => setStep(i + 2), (i + 1) * 340));
  }, [last]);

  useEffect(() => {
    const el = ref.current;
    if (!el || reducedMotion()) return;
    let wait = 0;
    const stop = onEntry(el, () => (wait = window.setTimeout(play, TYPED_IN_MS)));
    return () => {
      stop();
      clearTimeout(wait);
      timers.current.forEach(clearTimeout);
    };
  }, [play]);

  if (!figure) return <p className="figure">{text}</p>;
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
