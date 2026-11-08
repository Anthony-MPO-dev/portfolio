// One frame of a "decode": the share `progress` (0 to 1) of the text, from the left, is real; the rest shows random
// characters of the same kind (digit for digit, capital for letter). Spaces and punctuation never change.
const DIGITS = "0123456789";
const LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";

export function scramble(text: string, progress: number, random: () => number): string {
  const pick = (set: string) => set[Math.floor(random() * set.length)];
  return [...text]
    .map((ch, i, all) => {
      if (i / all.length < progress) return ch;
      if (/\d/.test(ch)) return pick(DIGITS);
      if (/[a-z]/i.test(ch)) return pick(LETTERS);
      return ch;
    })
    .join("");
}
