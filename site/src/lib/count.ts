// Count maths for the page's big numbers: read a figure such as "3x" or "13", then give the text to show at a point
// of the animation (0 to 1). It counts up from zero, or down from a start value (`from`). Eased out (fast, then
// slowing), rounded toward the start so the final figure only shows at the very end, with the figure's own decimals
// and the text around the number kept.
// Public API: parseFigure, figureAt, Figure. Used by components/count-up.tsx and fire-figure.tsx. Tests: count.test.ts.

export type Figure = { prefix: string; value: number; decimals: number; suffix: string };

export function parseFigure(text: string): Figure | null {
  const match = /^(\D*?)(\d+(?:\.(\d+))?)(.*)$/.exec(text);
  if (!match) return null;
  const [, prefix, number, decimals = "", suffix] = match;
  return { prefix, value: Number(number), decimals: decimals.length, suffix };
}

export function figureAt(figure: Figure, progress: number, from = 0): string {
  const { prefix, value, decimals, suffix } = figure;
  const scale = 10 ** decimals;
  const [start, end] = [Math.round(from * scale), Math.round(value * scale)];
  const eased = 1 - (1 - Math.min(Math.max(progress, 0), 1)) ** 3;
  const at = start + (end - start) * eased;
  const shown =
    progress >= 1 ? end : end > start ? Math.min(Math.floor(at), end - 1) : Math.max(Math.ceil(at), end + 1);
  return `${prefix}${(shown / scale).toFixed(decimals)}${suffix}`;
}
