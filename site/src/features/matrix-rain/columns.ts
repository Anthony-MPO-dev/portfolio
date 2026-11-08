// The columns of the character rain for a box of the given size: about one every 30 px (10 to 44), each a vertical
// string of 14 to 27 code-like glyphs falling in 5 to 14 s, already part-way through its fall when the page opens.
export const GLYPHS = "0123456789ABCDEF<>/{}[]=+*#$%&";

export type Column = { text: string; duration: number; delay: number; fall: number };

export function rainColumns(width: number, height: number, random: () => number): Column[] {
  const count = Math.min(44, Math.max(10, Math.floor(width / 30)));
  return Array.from({ length: count }, () => {
    const length = 14 + Math.floor(random() * 14);
    const text = Array.from({ length }, () => GLYPHS[Math.floor(random() * GLYPHS.length)]).join("\n");
    const duration = 5 + random() * 9;
    return { text, duration, delay: -random() * duration, fall: height + 40 };
  });
}
