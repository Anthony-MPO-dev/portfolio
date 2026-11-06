import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";

// PROTOTYPE: switcher between the directions. Shown in production on purpose (version 0 is for picking one).
export const DIRECTIONS = [
  { path: "/a", key: "A", name: "Schematic", note: "Light, like an engineering drawing. The credit pipeline draws itself as you scroll." },
  { path: "/b", key: "B", name: "Logstream", note: "Terminal and timeline. LogStream's flow, and healthmon closing the gate." },
  { path: "/c", key: "C", name: "Golden set", note: "Editorial, giant numbers. The 13 of 23 test questions fill in as you scroll." },
] as const;

type Key = (typeof DIRECTIONS)[number]["key"];

function currentTheme(): "light" | "dark" {
  const set = document.documentElement.dataset.theme;
  if (set === "light" || set === "dark") return set;
  return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function PrototypeBar({ current }: { current: Key }) {
  const navigate = useNavigate();
  const [theme, setTheme] = useState<"light" | "dark" | null>(null);
  const i = DIRECTIONS.findIndex((d) => d.key === current);
  const neighbour = (offset: number) => DIRECTIONS[(i + offset + DIRECTIONS.length) % DIRECTIONS.length].path;

  useEffect(() => setTheme(currentTheme()), []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.altKey || e.metaKey || e.ctrlKey || e.shiftKey) return;
      if ((e.target as HTMLElement).closest("input, textarea, [contenteditable]")) return;
      if (e.key === "ArrowLeft") navigate(neighbour(-1));
      if (e.key === "ArrowRight") navigate(neighbour(1));
    };
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  });

  const toggleTheme = () => {
    const next = currentTheme() === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem("theme", next);
    } catch {
      // private mode: the choice just isn't remembered
    }
    setTheme(next);
  };

  return (
    <nav className="proto-bar" aria-label="Switch design direction">
      <button type="button" onClick={() => navigate(neighbour(-1))} aria-label="Previous direction">
        ←
      </button>
      <Link to="/" aria-label={`Direction ${current}, ${DIRECTIONS[i].name}. Back to the list`}>
        {current} · {DIRECTIONS[i].name}
      </Link>
      <button type="button" onClick={() => navigate(neighbour(1))} aria-label="Next direction">
        →
      </button>
      <button type="button" onClick={toggleTheme} aria-label="Switch light or dark theme">
        {theme === "dark" ? "Light" : "Dark"}
      </button>
    </nav>
  );
}
