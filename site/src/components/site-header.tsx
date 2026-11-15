import { Link, useLocation } from "react-router";
import { contact, home } from "@/content/profile";
import { useLang } from "@/hooks/use-lang";
import { HTML_LANG, type Lang, pathIn, rememberLang } from "@/lib/lang";
import { ThemeToggle } from "./theme-toggle";
import "./site-header.css";

// The bar on top of every page: the name (a link home), the open-to-work status, the EN | PT switch (the same page in
// the other language; the choice is remembered, lib/lang.ts) and the theme switch.
// Public API: SiteHeader. Used by app/routes/home.tsx and app/routes/services.tsx.

const LANGS: { id: Lang; label: string; name: string }[] = [
  { id: "en", label: "EN", name: "English" },
  { id: "pt", label: "PT", name: "Português" },
];

export function SiteHeader() {
  const lang = useLang();
  const { pathname } = useLocation();
  return (
    <header className="top">
      <Link to={pathIn(lang, "/")}>{contact.name}</Link>
      <span className="top-status">{home[lang].profile.status}</span>
      <nav className="top-lang" aria-label={lang === "pt" ? "Idioma" : "Language"}>
        {LANGS.map((l, i) => [
          i > 0 && (
            <span key="sep" className="top-lang-sep" aria-hidden="true">
              |
            </span>
          ),
          <Link
            key={l.id}
            to={pathIn(l.id, pathname)}
            lang={HTML_LANG[l.id]}
            hrefLang={HTML_LANG[l.id]}
            title={l.name}
            aria-current={l.id === lang ? "page" : undefined}
            onClick={() => rememberLang(l.id)}
          >
            {l.label}
          </Link>,
        ])}
      </nav>
      <ThemeToggle lang={lang} />
    </header>
  );
}
