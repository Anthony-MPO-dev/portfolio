import { rainColumns } from "@/features/matrix-rain/columns";
import { reducedMotion } from "@/lib/entry";

// The green rain over the whole page when a resume file is saved (the effect Anthony chose, 22/11): the columns of the
// rain at the top of the site (matrix-rain/columns.ts), each falling once across the screen, then the layer fades and
// goes. Only transform and opacity move (chat.css, .rain-burst); it takes no clicks, and nothing happens with reduced
// motion. Public API: rainBurst. Used by: resume-panel.tsx. Tests: rain-burst.test.ts.
const GONE_MS = 2300; // the last column lands and the layer has faded by then (chat.css)

export function rainBurst() {
  if (reducedMotion()) return;
  const layer = document.createElement("div");
  layer.className = "rain-burst";
  layer.setAttribute("aria-hidden", "true");
  for (const column of rainColumns(innerWidth, innerHeight, Math.random)) {
    const span = document.createElement("span");
    span.dataset.t = column.text;
    span.style.setProperty("--fall", `${column.fall}px`);
    span.style.setProperty("--delay", `${(Math.random() * 0.4).toFixed(2)}s`);
    layer.append(span);
  }
  document.body.append(layer);
  setTimeout(() => layer.remove(), GONE_MS);
}
