import type { CSSProperties } from "react";

// Position of an element in a scroll scene: the CSS turns it into a slice of the scroll range (or a delay).
export const step = (i: number) => ({ "--i": i }) as CSSProperties;
