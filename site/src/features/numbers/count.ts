// Count-up maths for the page's big numbers: read a figure such as "3x" or "13", then give the text to show at
// a point of the animation (0 to 1). Eased out (fast, then slowing), rounded down so the final figure only shows
// at the very end, with the figure's own decimals and the text around the number kept.
// Public API: parseFigure, figureAt, Figure. Used by count-up.tsx. Tests: count.test.ts.

export type Figure = { prefix: string; value: number; decimals: number; suffix: string };

export function parseFigure(text: string): Figure | null {
  const match = /^(\D*?)(\d+(?:\.(\d+))?)(.*)$/.exec(text);
  if (!match) return null;
  const [, prefix, number, decimals = "", suffix] = match;
  return { prefix, value: Number(number), decimals: decimals.length, suffix };
}

export function figureAt(figure: Figure, progress: number): string {
  const { prefix, value, decimals, suffix } = figure;
  const scale = 10 ** decimals;
  const eased = 1 - (1 - Math.min(Math.max(progress, 0), 1)) ** 3;
  const shown = progress >= 1 ? value : Math.min(Math.floor(eased * value * scale), value * scale - 1) / scale;
  return `${prefix}${shown.toFixed(decimals)}${suffix}`;
}
