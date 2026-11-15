// The page's language, from its path: English at the root, Portuguese under /pt/ (same pages, same paths after it).
// The EN | PT switch keeps the visitor on the same page and remembers the choice; LANG_BOOT runs before paint and
// sends someone who chose Portuguese from an English page to its /pt/ twin. The first visit is always English: the
// browser's language is never read.
// Public API: Lang, langOf, pathIn, alternates, pageLinks, rememberLang, LANG_BOOT, SITE, LOCALE, HTML_LANG.
// Used by: app/root.tsx, the routes, components/site-header.tsx and every text module with an { en, pt } pair.
// Tests: lang.test.ts.

export type Lang = "en" | "pt";
export const SITE = "https://anthonymuniz.dev";
export const LOCALE: Record<Lang, string> = { en: "en-US", pt: "pt-BR" }; // numbers and dates
export const HTML_LANG: Record<Lang, string> = { en: "en", pt: "pt-BR" }; // lang and hreflang attributes
const OG_LOCALE: Record<Lang, string> = { en: "en_US", pt: "pt_BR" };

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
      [HTML_LANG.en, pathIn("en", pathname)],
      [HTML_LANG.pt, pathIn("pt", pathname)],
      ["x-default", pathIn("en", pathname)],
    ] as const
  ).map(([hrefLang, path]) => ({ tagName: "link", rel: "alternate", hrefLang, href: SITE + path }));

// A page's address in its language and the meta tags every page shares (og:url, og:locale, canonical, hreflang).
// page: the English path ("/" or "/services").
export function pageLinks(lang: Lang, page: string) {
  const url = SITE + pathIn(lang, page);
  const tags = [
    { property: "og:url", content: url },
    { property: "og:locale", content: OG_LOCALE[lang] },
    { tagName: "link", rel: "canonical", href: url },
    ...alternates(page),
  ];
  return { url, tags };
}

export function rememberLang(lang: Lang) {
  try {
    localStorage.setItem("lang", lang);
  } catch {
    // private mode: the choice just isn't remembered
  }
}

export const LANG_BOOT = `try{var p=location.pathname;if(localStorage.getItem("lang")==="pt"&&!/${PT.source}/.test(p))location.replace("/pt"+p+(location.search||"")+(location.hash||""))}catch(e){}`;
