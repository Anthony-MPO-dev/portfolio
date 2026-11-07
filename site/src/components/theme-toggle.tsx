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

export function ThemeToggle() {
  return (
    <button type="button" className="theme-toggle" onClick={toggleTheme} aria-label="Switch between light and dark theme">
      <span className="when-light">Dark</span>
      <span className="when-dark">Light</span>
    </button>
  );
}
