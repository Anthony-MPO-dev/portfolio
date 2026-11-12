// Pure helpers of the fact search's picture: the map's scale and how much of each result is typed so far.
// Public API: scaler, typedLengths. Used by: fact-search.tsx. Tests: map.test.ts.

type Point = { x: number; y: number };

// The facts spread over a 100x100 square with a margin, y pointing up; a question that lands outside stays inside.
export function scaler(points: Point[], pad = 6, size = 100) {
  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const clamp = (n: number) => Math.min(size - 3, Math.max(3, n));
  const span = size - 2 * pad;
  const scale = (v: number, lo: number, hi: number) => (hi === lo ? size / 2 : pad + (span * (v - lo)) / (hi - lo));
  return {
    sx: (x: number) => clamp(scale(x, x0, x1)),
    sy: (y: number) => clamp(size - scale(y, y0, y1)),
  };
}

// n characters typed so far, filling the texts one after the other.
export function typedLengths(texts: string[], n: number): number[] {
  let left = n;
  return texts.map((t) => {
    const k = Math.max(0, Math.min(t.length, left));
    left -= t.length;
    return k;
  });
}
