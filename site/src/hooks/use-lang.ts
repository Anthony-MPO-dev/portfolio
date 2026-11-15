import { useLocation } from "react-router";
import { langOf } from "@/lib/lang";

// The current page's language, from its path (lib/lang.ts): "pt" under /pt/, "en" elsewhere. Works while the pages
// are prerendered too, since every route renders with its own location.
// Public API: useLang. Used by: app/root.tsx, the routes, and every component with text in both languages.
// Tests: none of its own (one line over langOf, tested in lib/lang.test.ts).
export const useLang = () => langOf(useLocation().pathname);
