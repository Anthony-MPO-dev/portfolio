import { type RefObject, useEffect } from "react";

// Plays the page's entrances: marks each scene and .typed section visible once its top passes 65% of the screen, so
// the CSS plays its animation once, in full, on a timer (the page keeps scrolling; nothing waits on the scroll).
export function useReveal(root: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const el = root.current;
    if (!el) return;
    document.documentElement.classList.add("reveal-ready");
    const io = new IntersectionObserver(
      (entries) =>
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-visible");
          io.unobserve(entry.target);
        }),
      { rootMargin: "0px 0px -35% 0px" },
    );
    el.querySelectorAll(".scene, .typed").forEach((node) => io.observe(node));
    return () => io.disconnect();
  }, [root]);
}
