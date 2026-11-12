// Client of the fact search: GET /api/search/facts (the map, cached for an hour) and POST /api/search (a question).
// A network failure or an answer the page doesn't know is "offline"; nothing here throws.
// Public API: getFacts, searchFacts, Fact, Hit, SearchResult. Used by: fact-search.tsx. Tests: api.test.ts.

export type Fact = { id: number; section: string; text: string; x: number; y: number };
export type Hit = { id: number; score: number };
export type SearchResult =
  | { status: "ok"; hits: Hit[]; x: number; y: number }
  | { status: "invalid" | "rate_limited" | "unavailable" | "offline" };

const REFUSED = ["invalid", "rate_limited", "unavailable"] as const;

export async function getFacts(): Promise<Fact[] | null> {
  try {
    const response = await fetch("/api/search/facts");
    if (!response.ok) return null;
    const data = (await response.json()) as { facts?: Fact[] };
    return Array.isArray(data.facts) ? data.facts : null;
  } catch {
    return null;
  }
}

export async function searchFacts(q: string): Promise<SearchResult> {
  try {
    const response = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ q }),
      credentials: "same-origin",
    });
    const data = (await response.json()) as { status?: string; hits?: Hit[]; x?: number; y?: number };
    if (data.status === "ok" && Array.isArray(data.hits)) return { status: "ok", hits: data.hits, x: Number(data.x), y: Number(data.y) };
    return REFUSED.find((s) => s === data.status) ? { status: data.status as (typeof REFUSED)[number] } : { status: "offline" };
  } catch {
    return { status: "offline" };
  }
}
