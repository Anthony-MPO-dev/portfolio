import { type RefObject, useEffect } from "react";
import { reducedMotion } from "@/lib/entry";
import { scramble } from "@/lib/scramble";

// Section labels "decode" once as they come into view: their letters scramble for 0.7 s and settle, left to right,
// into the real text. About 20 text updates per label, then the real text for good; nothing with reduced motion.
const MS = 700;
const FRAME = 33;

export function useDecode(root: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const el = root.current;
    if (!el || reducedMotion()) return;
    const io = new IntersectionObserver(
      (entries) =>
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          io.unobserve(entry.target);
          decode(entry.target);
        }),
      { threshold: 0.5 },
    );
    el.querySelectorAll(".label").forEach((node) => io.observe(node));
    return () => io.disconnect();
  }, [root]);
}

// Changes the existing text nodes in place, so React keeps the nodes it rendered.
function decode(el: Element) {
  const nodes: [Text, string][] = [];
  const walk = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  while (walk.nextNode()) nodes.push([walk.currentNode as Text, walk.currentNode.nodeValue ?? ""]);
  const start = performance.now();
  let last = -FRAME;
  const frame = (now: number) => {
    const progress = Math.min(1, (now - start) / MS);
    if (now - last >= FRAME || progress === 1) {
      last = now;
      for (const [node, text] of nodes) node.nodeValue = scramble(text, progress, Math.random);
    }
    if (progress < 1) requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
}
