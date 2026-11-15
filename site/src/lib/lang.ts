// The page's language, from its path: English at the root, Portuguese under /pt/ (same pages, same paths after it).
// The EN | PT switch keeps the visitor on the same page and remembers the choice; LANG_BOOT runs before paint and
// sends someone who chose Portuguese from an English page to its /pt/ twin. The first visit is always English: the
// browser's language is never read.
// Public API: Lang, langOf, pathIn, alternates, rememberLang, LANG_BOOT, SITE, LOCALE. Used by: app/root.tsx, the
// routes, components/site-header.tsx and every text module with an { en, pt } pair. Tests: lang.test.ts.

export type Lang = "en" | "pt";
export const SITE = "https://anthonymuniz.dev";
export const LOCALE: Record<Lang, string> = { en: "en-US", pt: "pt-BR" };

const PT = /^\/pt(\/|$)/;

export const langOf = (pathname: string): Lang => (PT.test(pathname) ? "pt" : "en");

export function pathIn(lang: Lang, pathname: string): string {
  const english = pathname.replace(PT, "/");
  return lang === "en" ? english : `/pt${english}`;
}

// The hreflang links of a page: both versions, English as the default.
export const alternates = (pathname: string) =>
  (
    [
      ["en", pathIn("en", pathname)],
      ["pt-BR", pathIn("pt", pathname)],
      ["x-default", pathIn("en", pathname)],
    ] as const
  ).map(([hrefLang, path]) => ({ tagName: "link", rel: "alternate", hrefLang, href: SITE + path }));

export function rememberLang(lang: Lang) {
  try {
    localStorage.setItem("lang", lang);
  } catch {
    // private mode: the choice just isn't remembered
  }
}

export const LANG_BOOT = `try{var p=location.pathname;if(localStorage.getItem("lang")==="pt"&&!/^\\/pt(\\/|$)/.test(p))location.replace("/pt"+p+(location.search||"")+(location.hash||""))}catch(e){}`;
