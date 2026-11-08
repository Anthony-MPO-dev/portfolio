import { type CSSProperties, useEffect, useRef, useState } from "react";
import { type Column, rainColumns } from "./columns";
import "./rain.css";

// Character rain behind the top of the page. Built once on the client from the box size (the prerendered HTML has
// an empty box, so nothing shifts), then only CSS moves it; paused while off screen, never built with reduced motion.
// The parent needs `position: relative`.
export function MatrixRain() {
  const box = useRef<HTMLDivElement>(null);
  const [columns, setColumns] = useState<Column[]>([]);

  useEffect(() => {
    const el = box.current;
    if (!el || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    setColumns(rainColumns(el.clientWidth, el.clientHeight, Math.random));
    const io = new IntersectionObserver(([entry]) => el.classList.toggle("rain-off", !entry.isIntersecting));
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <div ref={box} className="rain" aria-hidden="true">
      {columns.map((c, n) => (
        <span key={n} style={{ "--d": `${c.duration}s`, "--delay": `${c.delay}s`, "--fall": `${c.fall}px` } as CSSProperties}>
          {c.text}
        </span>
      ))}
    </div>
  );
}
