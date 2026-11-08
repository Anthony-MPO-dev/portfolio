import { useEffect, useRef } from "react";
import { onEntry, reducedMotion } from "@/lib/entry";
import { figureAt, parseFigure } from "@/lib/count";
import "./count-up.css";

// A figure that counts up from zero, fast, when it comes into view. The HTML always holds the final figure (no JS,
// reduced motion, screen readers), and the digits' box keeps its final width so nothing around them shifts.
// Public API: CountUp. Used by features/support-agent/search-fix-scene.tsx. Logic tests: lib/count.test.ts.
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
