import { type CSSProperties, useEffect, useRef } from "react";
import { onEntry, reducedMotion } from "@/lib/entry";
import { figureAt, parseFigure } from "@/lib/count";
import "./count-up.css";

// A figure that counts, fast, when it comes into view (after `delay` ms): up from zero, or down from `from`. Counting
// down, the digits lean like italics at speed and straighten as they brake (count-up.css). The HTML always holds the
// final figure (no JS, reduced motion, screen readers), and the digits' box keeps its final width so nothing around
// them shifts.
// Public API: CountUp. Used by app/routes/home.tsx and features/support-agent/search-fix-scene.tsx.
// Logic tests: lib/count.test.ts.
type Props = { text: string; from?: number; delay?: number; ms?: number };

export function CountUp({ text, from = 0, delay = 0, ms = 900 }: Props) {
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    const el = ref.current;
    const figure = parseFigure(text);
    if (!el || !figure || reducedMotion()) return;
    el.style.minWidth = `${el.getBoundingClientRect().width}px`;
    el.textContent = figureAt(figure, 0, from);
    let frame = 0;
    let wait = 0;
    const play = () => {
      el.classList.toggle("is-falling", from > figure.value);
      const start = performance.now();
      const tick = (now: number) => {
        const progress = (now - start) / ms;
        el.textContent = figureAt(figure, progress, from);
        if (progress < 1) frame = requestAnimationFrame(tick);
      };
      frame = requestAnimationFrame(tick);
    };
    const stop = onEntry(el, () => (wait = window.setTimeout(play, delay)));
    return () => {
      stop();
      clearTimeout(wait);
      cancelAnimationFrame(frame);
      el.textContent = text;
      el.style.minWidth = "";
      el.classList.remove("is-falling");
    };
  }, [text, from, delay, ms]);
  return (
    <span className="count">
      <span className="num-sr">{text}</span>
      <span ref={ref} aria-hidden="true" style={{ "--ms": `${ms}ms` } as CSSProperties}>
        {text}
      </span>
    </span>
  );
}
