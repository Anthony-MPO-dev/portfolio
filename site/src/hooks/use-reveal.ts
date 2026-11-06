import { type RefObject, useEffect } from "react";

// Fallback for browsers without CSS scroll-driven animations: mark scenes as visible once they enter the viewport,
// so the CSS can play the same animation on a timer instead of on scroll.
export function useReveal(root: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const el = root.current;
    if (!el || CSS.supports("animation-timeline: view()")) return;
    document.documentElement.classList.add("reveal-ready");
    const io = new IntersectionObserver(
      (entries) =>
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-visible");
          io.unobserve(entry.target);
        }),
      { rootMargin: "0px 0px -25% 0px" },
    );
    el.querySelectorAll(".scene, .reveal").forEach((node) => io.observe(node));
    return () => io.disconnect();
  }, [root]);
}
