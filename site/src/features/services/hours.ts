// Calculator maths of the /services page: hours a team gets back in a year from the visitor's own numbers, the
// full-time people that makes, the year piling up month by month, and the cleaning of the form's fields. The page
// shows its assumptions next to the result: 46 working weeks, a full-time person at 40 hours a week. No currency:
// the optional cost of an hour is whatever number the visitor types.
// Public API: WORK_WEEKS, FULL_TIME_HOURS, hoursBack, fullTimePeople, monthlyHours, parseRate, clampInput.
// Used by features/services/calculator.tsx. Tests: hours.test.ts.

export const WORK_WEEKS = 46;
export const FULL_TIME_HOURS = 40 * WORK_WEEKS;

type Task = { people: number; hoursPerWeek: number; cutPercent: number };

const positive = (n: number) => (Number.isFinite(n) && n > 0 ? n : 0);

export function hoursBack({ people, hoursPerWeek, cutPercent }: Task): number {
  const cut = Math.min(positive(cutPercent), 100) / 100;
  return Math.round(positive(people) * positive(hoursPerWeek) * WORK_WEEKS * cut);
}

export const fullTimePeople = (hours: number) => Math.round((positive(hours) / FULL_TIME_HOURS) * 10) / 10;

export const monthlyHours = (total: number) => Array.from({ length: 12 }, (_, i) => Math.round((total * (i + 1)) / 12));

// "50", "42.5" or "42,5"; anything else, zero or below is null (the page then shows no value).
export function parseRate(text: string): number | null {
  const clean = text.trim().replace(",", ".");
  if (!/^\d+(\.\d+)?$/.test(clean)) return null;
  const rate = Number(clean);
  return rate > 0 ? rate : null;
}

export function clampInput(text: string, min: number, max: number): number {
  const n = Math.round(Number(text));
  return Number.isFinite(n) && text.trim() !== "" ? Math.min(max, Math.max(min, n)) : min;
}
