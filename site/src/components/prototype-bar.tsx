import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";

// PROTOTYPE: switcher between the three directions. Shown in production on purpose (version 0 is for picking one).
const DIRECTIONS = [
  { path: "/a", key: "A", name: "Schematic" },
  { path: "/b", key: "B", name: "Logstream" },
  { path: "/c", key: "C", name: "Golden set" },
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

  useEffect(() => setTheme(currentTheme()), []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t.closest("input, textarea, [contenteditable]")) return;
      if (e.key === "ArrowLeft") navigate(DIRECTIONS[(i + 2) % 3].path);
      if (e.key === "ArrowRight") navigate(DIRECTIONS[(i + 1) % 3].path);
    };
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, [i, navigate]);

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
      <button type="button" onClick={() => navigate(DIRECTIONS[(i + 2) % 3].path)} aria-label="Previous direction">
        ←
      </button>
      <Link to="/">
        {current} · {DIRECTIONS[i].name}
      </Link>
      <button type="button" onClick={() => navigate(DIRECTIONS[(i + 1) % 3].path)} aria-label="Next direction">
        →
      </button>
      <button type="button" onClick={toggleTheme} aria-label="Switch light or dark theme">
        {theme === "dark" ? "Light" : "Dark"}
      </button>
    </nav>
  );
}
