import { Link } from "react-router";
import { profile } from "@/content/profile";
import { ThemeToggle } from "./theme-toggle";
import "./site-header.css";

// The bar on top of every page: the name (a link home), the open-to-work status and the theme switch.
// Public API: SiteHeader. Used by app/routes/home.tsx and app/routes/services.tsx.
export function SiteHeader() {
  return (
    <header className="top">
      <Link to="/">{profile.name}</Link>
      <span className="top-status">{profile.status}</span>
      <ThemeToggle />
    </header>
  );
}
