import { describe, expect, it, vi } from "vitest";
import { alternates, LANG_BOOT, langOf, pageLinks, pathIn } from "./lang";

describe("langOf", () => {
  it("reads Portuguese from the /pt/ pages and English from the rest", () => {
    expect(["/pt", "/pt/", "/pt/services"].map(langOf)).toEqual(["pt", "pt", "pt"]);
    expect(["/", "/services", "/ptx", "/services/pt"].map(langOf)).toEqual(["en", "en", "en", "en"]);
  });
});

describe("pathIn", () => {
  it("gives the same page in the other language", () => {
    expect(pathIn("pt", "/")).toBe("/pt/");
    expect(pathIn("pt", "/services")).toBe("/pt/services");
    expect(pathIn("en", "/pt/")).toBe("/");
    expect(pathIn("en", "/pt")).toBe("/");
    expect(pathIn("en", "/pt/services")).toBe("/services");
  });

  it("leaves a page already in that language as it is", () => {
    expect(pathIn("pt", "/pt/services")).toBe("/pt/services");
    expect(pathIn("en", "/services")).toBe("/services");
  });
});

describe("alternates", () => {
  it("links both versions of a page for search engines, English as the default", () => {
    expect(alternates("/pt/services")).toEqual([
      { tagName: "link", rel: "alternate", hrefLang: "en", href: "https://anthonymuniz.dev/services" },
      { tagName: "link", rel: "alternate", hrefLang: "pt-BR", href: "https://anthonymuniz.dev/pt/services" },
      { tagName: "link", rel: "alternate", hrefLang: "x-default", href: "https://anthonymuniz.dev/services" },
    ]);
    expect(alternates("/").map((l) => l.href)).toEqual([
      "https://anthonymuniz.dev/",
      "https://anthonymuniz.dev/pt/",
      "https://anthonymuniz.dev/",
    ]);
  });
});

describe("pageLinks", () => {
  it("gives a page's address and the tags every page shares, in its language", () => {
    const { url, tags } = pageLinks("pt", "/services");
    expect(url).toBe("https://anthonymuniz.dev/pt/services");
    expect(tags.slice(0, 3)).toEqual([
      { property: "og:url", content: "https://anthonymuniz.dev/pt/services" },
      { property: "og:locale", content: "pt_BR" },
      { tagName: "link", rel: "canonical", href: "https://anthonymuniz.dev/pt/services" },
    ]);
    expect(tags.slice(3)).toEqual(alternates("/services"));
    expect(pageLinks("en", "/").tags[1]).toEqual({ property: "og:locale", content: "en_US" });
  });
});

// The boot script runs before paint, as a string: run that same string with a fake storage and location.
function boot(stored: string | null, pathname: string, search = "", hash = "") {
  const replace = vi.fn();
  const storage = {
    getItem: (k: string) => (k === "lang" ? stored : null),
  };
  new Function("localStorage", "location", LANG_BOOT)(storage, { pathname, search, hash, replace });
  return replace;
}

describe("LANG_BOOT", () => {
  it("sends a visitor who chose Portuguese to the same page in Portuguese", () => {
    expect(boot("pt", "/")).toHaveBeenCalledWith("/pt/");
    expect(boot("pt", "/services", "?a=1", "#calc")).toHaveBeenCalledWith("/pt/services?a=1#calc");
  });

  it("leaves everyone else where they are: no choice, English chosen, or already in Portuguese", () => {
    expect(boot(null, "/")).not.toHaveBeenCalled();
    expect(boot("en", "/services")).not.toHaveBeenCalled();
    expect(boot("pt", "/pt/")).not.toHaveBeenCalled();
    expect(boot("pt", "/pt/services")).not.toHaveBeenCalled();
  });

  it("does nothing when storage is blocked", () => {
    const blocked = {
      getItem: () => {
        throw new Error("SecurityError");
      },
    };
    const replace = vi.fn();
    expect(() => new Function("localStorage", "location", LANG_BOOT)(blocked, { pathname: "/", replace })).not.toThrow();
    expect(replace).not.toHaveBeenCalled();
  });
});
