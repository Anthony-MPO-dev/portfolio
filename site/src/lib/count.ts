// Count maths for the page's big numbers: read a figure such as "3x" or "13", then give the text to show at a point
// of the animation (0 to 1). It counts up from zero, or down from a start value (`from`). Eased out (fast, then
// slowing), rounded toward the start so the final figure only shows at the very end, with the figure's own decimals,
// its decimal point or comma, and the text around the number kept.
// Public API: parseFigure, figureAt, Figure. Used by components/count-up.tsx and fire-figure.tsx. Tests: count.test.ts.

// point: the decimal separator the figure was written with ("." in English, "," on the Portuguese pages).
export type Figure = { prefix: string; value: number; decimals: number; suffix: string; point: string };

export function parseFigure(text: string): Figure | null {
  const match = /^(\D*?)(\d+)(?:([.,])(\d+))?(.*)$/.exec(text);
  if (!match) return null;
  const [, prefix, whole, point = ".", decimals = "", suffix] = match;
  return { prefix, value: Number(`${whole}.${decimals || 0}`), decimals: decimals.length, suffix, point };
}

export function figureAt(figure: Figure, progress: number, from = 0): string {
  const { prefix, value, decimals, suffix, point } = figure;
  const scale = 10 ** decimals;
  const [start, end] = [Math.round(from * scale), Math.round(value * scale)];
  const eased = 1 - (1 - Math.min(Math.max(progress, 0), 1)) ** 3;
  const at = start + (end - start) * eased;
  const shown =
    progress >= 1 ? end : end > start ? Math.min(Math.floor(at), end - 1) : Math.max(Math.ceil(at), end + 1);
  return `${prefix}${(shown / scale).toFixed(decimals).replace(".", point)}${suffix}`;
}
