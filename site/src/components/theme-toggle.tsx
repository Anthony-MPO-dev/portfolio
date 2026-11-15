import type { Lang } from "@/lib/lang";
import "./theme-toggle.css";

// Light or dark switch. The boot script in root.tsx applies the saved choice before paint, and CSS (.when-light,
// .when-dark) picks the button's word, so neither the page nor the label flashes before React loads.
function currentTheme(): "light" | "dark" {
  const set = document.documentElement.dataset.theme;
  if (set === "light" || set === "dark") return set;
  return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function toggleTheme() {
  const next = currentTheme() === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  try {
    localStorage.setItem("theme", next);
  } catch {
    // private mode: the choice just isn't remembered
  }
}

export const WORDS = {
  en: { label: "Switch between light and dark theme", dark: "Dark", light: "Light" },
  pt: { label: "Trocar entre tema claro e escuro", dark: "Escuro", light: "Claro" },
};

export function ThemeToggle({ lang }: { lang: Lang }) {
  const t = WORDS[lang];
  return (
    <button type="button" className="theme-toggle" onClick={toggleTheme} aria-label={t.label}>
      <span className="when-light">{t.dark}</span>
      <span className="when-dark">{t.light}</span>
    </button>
  );
}
