import { reducedMotion } from "@/lib/entry";

// The green rain over the whole page when a resume file is saved (the effect Anthony chose, 22/11): a canvas layer
// that takes no clicks, a second and a half of falling characters in the site's green, then a fade. Nothing with
// reduced motion. Public API: rainBurst. Used by: resume-panel.tsx.
const GLYPHS = "01アイウエオカキクケコサシスセソ<>/{}[]=+*ABCDEFXYZ";
const SIZE = 18;
const RUN_MS = 1500;

export function rainBurst() {
  if (reducedMotion()) return;
  const canvas = document.createElement("canvas");
  canvas.setAttribute("aria-hidden", "true");
  canvas.width = innerWidth;
  canvas.height = innerHeight;
  canvas.style.cssText = "position:fixed;inset:0;z-index:100;pointer-events:none;transition:opacity .6s ease";
  document.body.append(canvas);
  const g = canvas.getContext("2d");
  if (!g) return canvas.remove();
  const color = getComputedStyle(document.documentElement).getPropertyValue("--accent-fill").trim() || "#3dfc8a";
  const columns = Array.from({ length: Math.ceil(canvas.width / SIZE) }, () => -Math.random() * 30);
  g.font = `600 ${SIZE}px "IBM Plex Mono", monospace`;
  g.fillStyle = color;
  const start = performance.now();
  const frame = (now: number) => {
    g.clearRect(0, 0, canvas.width, canvas.height);
    columns.forEach((y, i) => {
      for (let k = 0; k < 10; k++) {
        g.globalAlpha = (1 - k / 10) * 0.85;
        g.fillText(GLYPHS[(i * 7 + k * 3 + Math.floor(now / 60)) % GLYPHS.length], i * SIZE, (y - k) * SIZE);
      }
      columns[i] = y + 0.9 + (i % 5) * 0.12;
    });
    if (now - start < RUN_MS) return void requestAnimationFrame(frame);
    canvas.style.opacity = "0";
    setTimeout(() => canvas.remove(), 650);
  };
  requestAnimationFrame(frame);
}
