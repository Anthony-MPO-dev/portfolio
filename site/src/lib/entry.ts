// When the page's entrances play: an element enters once its top passes 65% of the screen. useReveal (scenes and
// .typed sections) and the big numbers (CountUp, FireFigure) share this point, so they start together.
// Public API: ENTRY_MARGIN, TYPED_IN_MS, onEntry, reducedMotion. Used by hooks/use-reveal.ts, components/count-up.tsx and
// components/fire-figure.tsx.

export const ENTRY_MARGIN = "0px 0px -35% 0px";

// How long a .typed block takes to type itself in: home-entrance.css starts the first block's skeleton at 250 + 180 ms
// and wipes it in 700 ms, so a figure is clear by about 1 s. Change the two together.
export const TYPED_IN_MS = 1000;

export const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

// Calls `run` once, when `el` enters. Returns the cleanup.
export function onEntry(el: Element, run: () => void) {
  const io = new IntersectionObserver(
    ([entry]) => {
      if (!entry.isIntersecting) return;
      io.disconnect();
      run();
    },
    { rootMargin: ENTRY_MARGIN },
  );
  io.observe(el);
  return () => io.disconnect();
}
