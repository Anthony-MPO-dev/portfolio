import type { CSSProperties } from "react";

// An element's turn in its scene: the CSS turns it into a delay of i x 140 ms.
export const step = (i: number) => ({ "--i": i }) as CSSProperties;
